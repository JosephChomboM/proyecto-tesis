# Apply progress: Forecasting work unit

Status: complete for tasks 3.1 and 3.2. Standard mode (`strict_tdd: false`).
Scope: `src/restaurante/forecast.py`, `tests/test_forecast.py` only; task checkboxes updated after passing execution.

## Behavior

- Ingredient forecasts use only dates strictly before origin, aggregate duplicate demand dates, and fill missing calendar days with zero consumption. RF requires 56 distinct recorded dates; otherwise explicit seasonal, mean, or no-history fallback applies. Future predictions are recursive, deterministic and nonnegative.
- Purchase planning uses isolated virtual FIFO lots, same-day-expiry eligibility, delayed receipts, pack rounding, fixed safety-stock targets, virtual receipt expiry and stock carryover. Existing/planned stock is consumed only once. Inputs and operational database remain unchanged.
- No accuracy score, expert judgment, real calibration or lost-sales estimate is fabricated.

## Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused tests | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_forecast.py -q` — exit 0; 25 passed in 1.89s. |
| Lint | `.venv/bin/ruff check src/restaurante/forecast.py tests/test_forecast.py` — exit 0; all checks passed. |
| Format | `.venv/bin/ruff format --check src/restaurante/forecast.py tests/test_forecast.py` — exit 0; 2 files already formatted. |
| Runtime harness | Inline Python imports actual module, creates 90-day labeled synthetic demand/catalog plus 15 kg lot, calls RF forecast then purchase plan for 2026-04-01 through 2026-04-07, asserts seven forecast/plan rows, safety balance and unchanged source lots — exit 0; Random Forest, 7/7 rows, 80 kg planned, S/320 estimated. |
| Rollback boundary | Remove the two owned files and clear only task 3.1/3.2 checkboxes; preserve all operational SQLite files and other work units. |

## Workload and limits

456 authored lines across implementation/tests. Local workspace delivery only; no repository, commit or PR was requested. A future publication can split forecast generation and virtual purchasing behavior into separate review units with their covering tests. No maintainer size exception is asserted.

Missing sales days are assumed zero, and consumed demand cannot reveal rejected/lost sales. Safety stock is a configured quantity, not a measured probabilistic service level. Advanced model comparison remains pending research scope.
