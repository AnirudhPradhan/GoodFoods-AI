import os
import json
import logging
from typing import Any, Dict, List
from dotenv import load_dotenv

load_dotenv()
from huggingface_hub import InferenceClient
from tools import TOOL_REGISTRY, execute_tool, tools_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GoodFoodsHF")

# -------------------------------------------------------
# Load HuggingFace API Key from Environment
# -------------------------------------------------------
HF_API_KEY = os.getenv("HF_TOKEN")

if HF_API_KEY is None or HF_API_KEY.strip() == "":
    raise EnvironmentError(
        "\n\n❌ Missing HF_API_KEY.\n"
        "Please create a HF token from https://huggingface.co/settings/tokens\n"
        "and set it as an environment variable:\n\n"
        "Windows:\n    set HF_API_KEY=your_token_here\n\n"
        "mac/Linux:\n    export HF_API_KEY=your_token_here\n\n"
    )

MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"


# Create HF inference client
client = InferenceClient(
    model=MODEL_ID,
    token=HF_API_KEY,
)



# -------------------------------------------------------
# HF Chat wrapper (OpenAI-style)
# -------------------------------------------------------
def hf_chat(messages: List[Dict[str, str]], max_tokens: int = 1024):
    """
    Wraps HuggingFace chat API output so it behaves like OpenAI/Groq.
    """
    response = client.chat_completion(
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.6,
    )
    return response.choices[0].message["content"]


# -------------------------------------------------------
# SYSTEM + PLANNER PROMPTS
# -------------------------------------------------------

# In agent.py

SYSTEM_PROMPT = """
You are the GoodFoods Reservation AI.

RULES:
1. NEVER call a tool until ALL required slots are known:
   - restaurant_id or restaurant name
   - time (ISO or natural language)
   - party_size

2. If ANY of these are missing:
   → ASK A CLEAR QUESTION to fill the missing slots.
   → DO NOT call any tool yet.

3. Required slot behavior:
   - If user says "book me a table" → ask:
       "Sure! Which restaurant, for how many people, and at what time?"
   - If user gives restaurant only → ask for time + party size.
   - If user gives time only → ask for restaurant + party size.
   - If user gives party size only → ask for restaurant + time.

4. After ALL slots are collected:
   → Use the appropriate tool (usually search_restaurants then book_table).

5. NEVER provide real-world information (phone numbers, addresses, websites).
   Only use tool results.

6. Tool call format MUST be:

   TOOL: <tool_name>
   ARGS: { json }

7. After tool execution, summarize the result for the user.
   CRITICAL: If the tool returns a list of restaurants, YOU MUST LIST the top 3-4 options by name with their rating and price. Do not just say "I found some restaurants."
"""

PLANNER_PROMPT = """
You are the GoodFoods planner.

Your job:
- Extract intent
- Identify missing slots
- Suggest tools ONLY when all required slots are available.
- RETAIN information from previous turns.

Required slots for booking:
- restaurant_id or restaurant name
- party_size
- time

Required slots for search or recommendation:
- city (Mandatory)

If any required slot is missing:
   recommended_tools must be an empty list.

Examples:
User: "book me a table"
→ recommended_tools = []

User: "book a table for 4"
→ recommended_tools = []

User: "mujhe acha resturant bolo"
→ intent = "recommend_restaurants"
→ recommended_tools = []
→ missing_slots = ["city"]

User: "suggest me"
→ intent = "recommend_restaurants"
→ recommended_tools = []
# If city is known from context, recommended_tools would be ["recommend_restaurants"]
→ missing_slots = ["city"] 

User: "book a table at Karim's for 4 at 8pm"
→ recommended_tools = ["search_restaurants", "book_table"]

Always output JSON:
{
 "intent": "...",
 "slots": {...},
 "recommended_tools": [],
 "missing_slots": [...]
}
"""

# -------------------------------------------------------
# Purify conversation
# -------------------------------------------------------
def _sanitize_history(messages):
    clean = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            if i + 1 >= len(messages) or messages[i+1].get("role") != "tool":
                continue
        clean.append(msg)
    return clean


# -------------------------------------------------------
# Planner: first pass
# -------------------------------------------------------
def _generate_plan(messages):
    snapshot = messages[-20:]

    planner_msgs = [
        {"role": "system", "content": PLANNER_PROMPT},
        {"role": "user", "content": json.dumps(snapshot)}
    ]

    try:
        raw = hf_chat(planner_msgs, max_tokens=500)

        # JSON extraction
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].strip()

        plan = json.loads(raw)

    except Exception as e:
        logger.error(f"Planner failed: {e}")
        plan = {
            "intent": "other",
            "slots": {},
            "recommended_tools": [],
            "reasoning": "planner_error"
        }

    # validate tools
    plan["recommended_tools"] = [
        t for t in plan.get("recommended_tools", []) if t in TOOL_REGISTRY
    ]

    return plan


# -------------------------------------------------------
# Parse tool call from assistant
# -------------------------------------------------------
def detect_tool_call(text: str):
    """
    Expected format from the model:

    TOOL: tool_name
    ARGS: { ... }
    """
    if "TOOL:" not in text:
        return None

    try:
        tool = text.split("TOOL:")[1].split("\n")[0].strip()
        args_json = text.split("ARGS:")[1].strip()
        args = json.loads(args_json)
        return {"name": tool, "args": args}
    except:
        return None


# -------------------------------------------------------
# MAIN AGENT LOGIC
# -------------------------------------------------------
def run_agent(messages: List[Dict[str, Any]]):
    # Clean old dangling messages
    messages = _sanitize_history(messages)

    # 1. Planner
    plan = _generate_plan(messages)

    plan_json = json.dumps({
        "intent": plan.get("intent"),
        "slots": plan.get("slots"),
        "recommended_tools": plan.get("recommended_tools"),
        "reasoning": plan.get("reasoning")
    })

    orchestrator_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Planner directive: {plan_json}"}
    ] + messages

    # 2. First assistant -> may include tool call
    try:
        assistant_text = hf_chat(orchestrator_messages, max_tokens=1024)
    except Exception as e:
        return {"content": f"HF API Error: {e}", "plan": plan, "used_tools": []}

    tool_call = detect_tool_call(assistant_text)

    if not tool_call:
        # Normal assistant answer
        return {
            "content": assistant_text,
            "plan": plan,
            "used_tools": []
        }

    # 3. Execute tool
    tool_name = tool_call["name"]
    tool_args = tool_call["args"]

    tool_output = execute_tool(tool_name, tool_args)

    orchestrator_messages.append({
        "role": "assistant",
        "content": assistant_text,
        "tool_calls": [{
            "id": "call_1",
            "type": "function",
            "function": {"name": tool_name, "arguments": json.dumps(tool_args)}
        }]
    })

    orchestrator_messages.append({
        "role": "tool",
        "tool_call_id": "call_1",
        "name": tool_name,
        "content": tool_output
    })

    # 4. Final answer after tool execution
    try:
        final_answer = hf_chat(orchestrator_messages, max_tokens=1024)
    except:
        final_answer = f"Executed tool `{tool_name}`. Result: {tool_output}"

    return {
        "content": final_answer,
        "plan": plan,
        "used_tools": [tool_name]
    }
