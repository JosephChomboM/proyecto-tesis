# Design: Functional restaurant system with demand forecasting

## Technical Approach
Implement CAT/OPS/PLAN/UI specifications as a local Python package with Streamlit presentation and SQLite transactions. Inspection confirms no existing application conventions or schemas to preserve. Installed Python 3.12 environment provides Streamlit, Pandas, NumPy, scikit-learn, Plotly, pytest and Ruff.

## Architecture Decisions
| Choice | Alternative | Rationale |
|---|---|---|
| SQLite service layer | UI-managed dataframes | Durable operations, foreign keys, atomic multi-ingredient sales |
| Streamlit Spanish interface | Separate API/frontend | PDF's stack; useful local delivery without hosting work |
| Separate demo/own files | Shared flag-filtered database | Prevent synthetic and real operational data mixing |
| Recorded ingredient consumption | Recompute history from current recipes | Recipe edits must not rewrite historical demand |
| RF plus explicit baseline | Mandatory neural runtime | Useful operations first; heavy comparison remains research work |

## Data Flow
`app.py -> RestaurantService -> SQLite`
`demand_history -> forecast -> purchase_plan -> CSV/UI`

Purchase planning runs a separate chronological virtual lot ledger: expire lots, calculate demand plus safety minus eligible balance, round any required receipt up to packs, assign that virtual receipt its shelf life, consume predicted demand FIFO, then carry remaining stock to the next day. Existing stock and planned receipts are allocated once; virtual purchases never mutate the operational database.

Each mutation validates inputs then executes inside one transaction. Sales reserve all requirements before modifying lots, consume FIFO ordered by receipt date/id, snapshot dish prices and ingredient quantities, and commit once. Insufficient stock rolls back everything. Request keys are unique per operation; identical replay returns original id, conflicting payload raises a domain error. Expired stock cannot be sold; expiration processing is idempotent. Business dates use `ZoneInfo('America/Lima')`; same-day-expiry lots remain usable through that date.

## File Changes
| File | Action | Responsibility |
|---|---|---|
| `src/restaurante/db.py` | Create | Schema, connections, foreign keys, transactional helpers |
| `src/restaurante/service.py` | Create | Catalog, operations, history, stock, demand contracts |
| `src/restaurante/seed.py` | Create | Idempotent labeled demo initialization |
| `src/restaurante/forecast.py` | Create | Past-only forecasts and pack-aware purchase plans |
| `src/restaurante/__init__.py` | Create | Package export |
| `app.py`, `.streamlit/config.toml` | Create | Spanish workflows and presentation |
| `pyproject.toml`, `.gitignore` | Create | Dependencies, test/lint setup, ignored local data |
| `tests/test_service.py`, `tests/test_forecast.py`, `tests/test_app.py` | Create | Behavior verification |
| `README.md`, `docs/traceability.md` | Create | Usage, limits and PDF mapping |

## Interfaces / Contracts
`RestaurantService(db_path)` initializes an empty schema. Domain errors subclass `ValueError`; UI catches them. Methods return created integer ids or Pandas DataFrames:

- `ingredients(include_inactive=False)` columns: `id,name,unit,cost,pack_size,shelf_life_days,safety_stock,active`.
- `save_ingredient(name,unit,cost,pack_size,shelf_life_days,safety_stock,ingredient_id=None)`; `set_ingredient_active(id,active)`.
- `dishes(include_inactive=False)` columns: `id,name,price,active`; `save_dish(name,price,dish_id=None)`; `set_dish_active(id,active)`.
- `recipe(dish_id)` columns: `ingredient_id,quantity`; `set_recipe(dish_id,items)` where items maps ingredient id to quantity.
- `receive_purchase(ingredient_id,quantity,unit_cost,received_on,expires_on,request_key)`; `record_sale(items,sold_on,request_key)` where items maps dish id to positive integer portions.
- `record_waste(ingredient_id,quantity,reason,occurred_on,request_key)`; `expire_stock(as_of)`.
- `stock(as_of)` columns: `ingredient_id,name,unit,available,expired,cost,pack_size,safety_stock`.
- `lots()` columns include ingredient id, remaining quantity, receipt and expiry dates; `sales()`, `purchases()`, `waste()` expose immutable audit history.
- `demand_history()` columns: `date,ingredient_id,quantity,source`; operational rows derive immutable consumption, demo history is a separate table explicitly labeled synthetic.
- `forecast_demand(history,ingredients,origin,horizon=7)` returns `date,ingredient_id,predicted,method,history_days`; `purchase_plan(predictions,lots,ingredients,safety_factor=1.0)` returns demand, eligible stock, safety, suggested quantity and estimated cost per ingredient/date.

Schema entities: metadata/version/seed marker; ingredients; dishes; recipes; purchases/lots; sales/lines/consumption; waste; idempotency keys/payload hashes; demo demand. Unit changes after recorded movements are rejected. No destructive catalog deletes.

## Testing Strategy
Use temporary SQLite databases to test restart persistence, full rollback, FIFO, expiry, replay/conflict, finite inputs and historical recipe independence. Forecast tests alter future observations and verify unchanged origin predictions; test empty history and expiring-stock/pack rounding. Streamlit AppTest exercises mode isolation and operational forms.

## Threat Matrix
N/A — no application routing, shell/subprocess execution, VCS automation, executable classification or process integration. Parameterized SQLite statements protect data boundaries.

## Migration / Rollout
No existing migration required. Default paths: `data/demo.sqlite3` and `data/restaurant.sqlite3`. Explicit mode choice precedes initialization; seeding only touches the demo file once. Backups precede future schema changes. Access control: local single trusted administrator, no public deployment.

## Open Questions
None blocking. Official calibration, human validation and XGBoost/LSTM research comparisons remain documented future research work.
