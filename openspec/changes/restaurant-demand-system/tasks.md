# Tasks: Functional restaurant system with demand forecasting

## Review Workload Forecast
| Field | Value |
|---|---|
| Estimated authored lines | 1,500–2,500 |
| Suggested split | Persistence/operations; forecasting; interface/integration |
| Delivery strategy | Local workspace implementation; no Git repository or PR requested |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

PR chaining is only a future publication recommendation. No maintainer exception or chain strategy is assumed; local implementation is authorized and does not require a PR decision.

### Suggested Work Units
| Unit | Focused tests | Runtime harness | Rollback boundary |
|---|---|---|---|
| Operations | `.venv/bin/python -m pytest tests/test_service.py` | Temporary database purchase → sale → reopen | Service/schema/seed and service tests; preserve user databases |
| Forecasting | `.venv/bin/python -m pytest tests/test_forecast.py` | Seed history → seven-day forecast → purchase plan | Forecast module and its tests |
| Interface | `.venv/bin/python -m pytest tests/test_app.py` | Streamlit AppTest demo/own workflows | App/theme/docs and app tests |

## Phase 1: Persistence and catalog

- [x] 1.1 Create `pyproject.toml`, `.gitignore`, `src/restaurante/__init__.py` with dependencies and pytest/Ruff configuration.
- [x] 1.2 Create `src/restaurante/db.py` schema, metadata, transactions, foreign keys and separate demo-history storage.
- [x] 1.3 Create catalog/recipe methods in `src/restaurante/service.py`; validate inputs and protect history/units (CAT-1/2).
- [x] 1.4 Add catalog/restart tests in `tests/test_service.py`.

## Phase 2: Restaurant operations

- [x] 2.1 Implement purchase receipts, FIFO lots, expiration and waste audit in `src/restaurante/service.py` (OPS-1).
- [x] 2.2 Implement atomic recipe-based sales and immutable price/consumption snapshots in `src/restaurante/service.py` (OPS-2).
- [x] 2.3 Implement payload-aware request idempotency in `src/restaurante/service.py` (OPS-3).
- [x] 2.4 Extend `tests/test_service.py` for rollback, FIFO, expiry, replay/conflict, invalid values and recipe edits.
- [x] 2.5 Create `src/restaurante/seed.py` with idempotent labeled demo stock/catalog and separate synthetic demand history.

## Phase 3: Forecasting

- [x] 3.1 Create `src/restaurante/forecast.py` with past-only RF/baseline forecasts and chronological virtual-lot purchase planning; allocate stock once with expiry, safety and packs (PLAN-1/2).
- [x] 3.2 Create `tests/test_forecast.py` for future-data isolation, empty history, expiry, pack rounding and multi-day depletion/carryover.

## Phase 4: Interface and verification

- [x] 4.1 Create `app.py` and `.streamlit/config.toml` for explicit data mode, dashboard, catalog, purchases, sales, stock/waste, forecasts and CSV exports (UI-1/2).
- [x] 4.2 Create `tests/test_app.py` to exercise demo/own isolation and purchase-to-sale dashboard updates.
- [x] 4.3 Create `README.md` and `docs/traceability.md` with startup, backups, single-admin limits and pending thesis evidence.
- [x] 4.4 Run complete pytest and Ruff checks; inspect running interface; record verification evidence and update testing capabilities in `openspec/config.yaml`.
