# Proposal: Functional restaurant system with demand forecasting

## Intent
Give restaurant administrators a working system for daily operations and ingredient purchasing informed by forecasts. Operational functionality is primary; the PDF motivates forecasting (OE1–OE4, pp. 8–9) and Python/Streamlit (pp. 14–16). Handoff revision 2 supersedes revision 1.

## Scope
### In Scope
- Separate labeled demo and initially empty own-restaurant SQLite databases, selected explicitly without silent resets.
- Persist ingredients, dishes, recipes, purchases, expiring stock lots, sales, and waste.
- Maintain catalogs with safe disabling; receive purchases; consume valid FIFO stock atomically from recipe-based sales; reject invalid quantities, insufficient stock, and duplicate execution.
- Show dashboard, inventory/expiry alerts, history, and CSV exports.
- Forecast daily ingredient demand and suggest purchases net of eligible stock, safety stock, and pack sizes, without executing orders.
- Seed demo history; document remaining research work.

### Out of Scope
- Billing, payments, multi-user hosting/authentication, production deployment, and automated supplier orders.
- Complete research experiments, fabricated calibration, expert/SUS responses, or guaranteed thesis results. XGBoost/LSTM comparison remains later research work.

## Capabilities
### New Capabilities
- `restaurant-catalog`: ingredients, dishes, recipes, units, pack sizes, costs, safe disabling.
- `restaurant-operations`: transactional sales/purchases, FIFO lots, expiry, waste, idempotency, audit history.
- `inventory-planning`: past-only forecasts and expiry-aware purchase suggestions.
- `restaurant-prototype`: Spanish workflows, dashboard, exports, and separate demo/own data.

### Modified Capabilities
None.

## Approach
Build a local single-administrator Streamlit application over a Python service layer and SQLite transactions. Use America/Lima business dates. Reject nonfinite/negative inputs, exclude expired lots, and preserve historical records. Use Random Forest with sufficient history and an explicit baseline otherwise. Label synthetic demo assumptions and pending research evidence clearly.

## Affected Areas
| Area | Impact | Description |
|---|---|---|
| `src/restaurante/` | New | Persistence, operations, forecasting |
| `app.py`, `data/` | New | UI and separate databases |
| `tests/`, `pyproject.toml` | New | Validation and dependencies |
| `README.md`, `docs/` | New | Usage and thesis traceability |

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Inventory corruption | Medium | Atomic writes, FIFO, idempotency tests |
| Demo confused with evidence | High | Separate files and persistent labels |
| Forecast overconfidence | Medium | Show method/history limitations |

## Rollback Plan
Back up local SQLite files before schema changes; remove introduced application files to restore the source-only workspace. Preserve PDF and SDD artifacts.

## Dependencies
Python, SQLite, Pandas/NumPy, Streamlit, scikit-learn; available locally.

## Success Criteria
- [ ] Purchases and sales persist with accurate stock/history.
- [ ] Invalid, expired, duplicate, or insufficient-stock operations cannot corrupt inventory.
- [ ] Administrators can export useful purchase suggestions.
- [ ] Demo/own data remain isolated and research limitations visible.
