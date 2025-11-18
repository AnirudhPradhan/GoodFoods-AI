# GoodFoods AI – Use Case & Strategy

## 1. Problem Statement
GoodFoods operates dozens of restaurant formats across the city. Manual reservation handling causes:
- Low table-utilization during shoulder hours because staff cannot upsell or cross-route guests fast enough.
- Fragmented visibility into loyalty tiers and feedback, so high-value diners receive generic treatment.
- No consistent playbook for pop-up events or overflow routing, forcing calls and walk-ins back to phone queues.

## 2. Opportunities Beyond Basic Booking
1. **Dynamic capacity brokerage** – Re-route demand across nearby venues based on real-time utilization and wait times.
2. **Personalized upsell loops** – Trigger SMS follow-ups, chef table offers, or event invites when loyalty or occasion signals warrant it.
3. **Operational intelligence** – Feed aggregated intent + feedback data into staffing forecasts and menu planning.

## 3. Success Metrics & ROI Hypotheses
| Metric | Baseline | Target | Notes |
| --- | --- | --- | --- |
| Table utilization (peak) | 72% | 82% | Better routing + pre-qualification |
| Self-serve booking conversion | 45% | 65% | Reduction in call-center load |
| High-tier loyalty retention | +0% | +8% | Personalized perks + proactive outreach |
| Manual handling cost / booking | \$2.10 | \$1.00 | Agent handles FAQs + data entry |
| Feedback capture rate | 12% | 35% | Automated post-meal prompts |

ROI expectation: ~4–5 month payback assuming 10k monthly bookings, \$40 average ticket, 10% incremental throughput, and partial call-center savings.

## 4. Vertical Expansion & Adjacent Plays
- **Franchise/partner rollout** – White-label the MCP tool registry so multi-brand groups can plug in their POS/CRM via adapters.
- **Hospitality & salons** – The capacity + loyalty orchestration mirrors appointment-heavy verticals.
- **Events & catering** – Extend the planner to coordinate multi-venue proposals, bundling inventory, logistics, and feedback loops.

## 5. Competitive Advantages
1. **MCP-native extensibility** – Tool schemas make it simple to add inventory, marketing, or analytics endpoints without rewriting the agent loop.
2. **Planner + executor split** – Intent classification, slot memory, and orchestration telemetry give ops stakeholders transparency lacking in off-the-shelf bots.
3. **Data-rich seeding** – The system already models menus, events, loyalty, and feedback, enabling advanced analytics and personalization from day one.

## 6. Stakeholders & Timeline
- Primary: Head of Operations, Digital CX lead, GM of each concept.
- Secondary: Marketing/CRM, Revenue management, Host staff.
- Pilot timeline: 2 weeks integration, 1 week staff enablement, 2 weeks A/B vs. control stores.

## 7. Risks & Mitigations
- **Model outages** → multi-model failover, cached recommendations.
- **Data freshness** → incremental sync endpoints + manual override UI.
- **Change management** → embed transcripts and planner insights in ops dashboards for human review.

## 8. Future Enhancements
Voice IVR, POS writebacks, automated staffing suggestions, LangGraph-based deterministic fallbacks for SLA-critical flows.

