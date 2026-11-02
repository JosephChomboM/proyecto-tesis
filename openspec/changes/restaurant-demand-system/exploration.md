## Exploration: Functional restaurant system with demand forecasting

### Current State
The workspace initially contains only the 35-page thesis PDF. No application exists. The PDF proposes demand forecasting and Streamlit (objectives pp. 8–9, tools pp. 14–16). The user's clarification establishes a functional restaurant system as the primary deliverable; handoff revision 2 supersedes the research-workbench interpretation.

### Affected Areas
- `src/restaurante/` — persistence, catalog, recipes, transactional sales and purchases, FIFO inventory, waste, forecasting.
- `app.py` — Spanish daily administrator workflows and dashboard.
- `data/` — separate demo and own-restaurant SQLite files.
- `tests/` — atomicity, idempotency, expiry, validation, forecasting isolation, interface integration.
- `README.md`, `docs/` — local usage and thesis traceability.

### Approaches
1. **Python service layer, SQLite, and Streamlit** — share testable business rules with a local Spanish interface.
   - Pros: follows PDF tools, offline persistence, atomic transactions, fast operational delivery.
   - Cons: local single-administrator scope; later hosting requires access controls.
   - Effort: High.
2. **Separate API and custom frontend** — store operations behind a web service.
   - Pros: future concurrent-user support.
   - Cons: additional infrastructure and deployment beyond the requested local system.
   - Effort: High.

### Recommendation
Implement approach 1. Provide explicit startup choice between a labeled demo restaurant and a separate initially empty own-restaurant database; never silently overwrite or reset either. Administrators maintain ingredients, dishes and recipes, receive expiring stock lots, record recipe-based sales, inspect stock/waste, and export history and purchasing suggestions. Sales consume nonexpired FIFO lots atomically and reject insufficient stock without partial changes. Request keys prevent duplicate execution. Forecast daily ingredient demand from past observations using Random Forest when history permits and an explicit baseline otherwise. Suggestions account for stock surviving the target date, safety stock, and pack rounding; they never place orders. Use America/Lima dates. Research model comparisons remain secondary future support, with no fabricated calibration or human-study evidence.

### Risks
- Operational corruption from invalid quantities, expired stock, retries, or partial writes requires transaction tests.
- Demo history and assumed recipes/prices are demonstration inputs, not calibrated thesis evidence.
- Sparse history limits forecasts; method and available observations must remain visible.
- Local single-administrator operation does not establish safe multi-user hosting.

### Ready for Proposal
Yes. Revision 2 authorizes a functional local restaurant system with persisted operations and forecast-assisted purchasing. No PR, hosting, authentication, or complete research-study delivery was requested.
