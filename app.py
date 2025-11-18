import streamlit as st

from agent import run_agent
from database import init_db

# Initialize DB on first load
init_db()

st.set_page_config(page_title="GoodFoods AI", layout="wide")
st.title("🍽️ GoodFoods – India’s Smart Dining Assistant")

# ---------------------------
# Session State Initialization
# ---------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "plans" not in st.session_state:
    st.session_state.plans = []

if "user_lang" not in st.session_state:
    st.session_state.user_lang = "English"

# ---------------------------
# Sidebar
# ---------------------------
with st.sidebar:
    st.header("⚙️ Agent Insights")

    # Language toggle
    lang_choice = st.radio("Language", ["English", "हिन्दी"], index=0)
    st.session_state.user_lang = lang_choice

    st.divider()

    # Planner snapshot
    if st.session_state.plans:
        latest_plan = st.session_state.plans[-1]
        st.subheader("🧠 Latest Planner Snapshot")

        st.write(f"**Intent:** {latest_plan.get('intent', 'n/a')}")
        st.caption("Suggested Tools")

        tools_list = latest_plan.get("recommended_tools") or []
        if tools_list:
            st.code(", ".join(tools_list))
        else:
            st.text("No specific tools suggested.")

        st.caption("Extracted Slots")
        st.json(latest_plan.get("slots", {}))
    else:
        st.info("Planner insights will appear here after your first query.")

# ---------------------------
# Chat History
# ---------------------------
st.divider()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ---------------------------
# Chat Input
# ---------------------------
if prompt := st.chat_input("Ask GoodFoods AI anything…"):
    # Record user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    # Inject language preference
    st.session_state.messages.append({
        "role": "system",
        "content": f"user_language:{st.session_state.user_lang}"
    })

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                agent_result = run_agent(st.session_state.messages)

                response_text = agent_result.get("content", "I had trouble formulating a response.")
                plan = agent_result.get("plan")

                st.markdown(response_text)

                st.session_state.messages.append({"role": "assistant", "content": response_text})

                if plan:
                    st.session_state.plans.append(plan)

            except Exception as error:
                error_text = (
                    "Sorry, I ran into an issue contacting the AI service. "
                    "Please try again in a moment."
                )
                st.error(error_text)
                st.caption(f"Details: {error}")

                st.session_state.messages.append({"role": "assistant", "content": error_text})
