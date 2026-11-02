# Apply progress: integration and runtime verification

Status: task 4.4 complete. Standard mode (`strict_tdd: false`, preserving the initialization decision).
Scope: `openspec/config.yaml`, this evidence artifact, and task 4.4 checkbox. Application/source changes remain owned by their implementation units.

## Work Unit Evidence

| Evidence | Exact command/scenario and result |
|---|---|
| Full workspace tests | `.venv/bin/python -m pytest -q` — exit **0**, `57 passed in 3.61s` (27 service, 25 forecast, 5 Streamlit AppTest cases). |
| Full lint | `.venv/bin/ruff check .` — exit **0**, `All checks passed!`. |
| Build/syntax | `.venv/bin/python -m compileall -q app.py src/restaurante` — exit **0**, no diagnostic output. This is compilation verification, not a deployment or distribution-package build. |
| Real integration harness | `PYTHONPATH=src .venv/bin/python - <<'PY'` inline temporary-DB harness: instantiate service → `seed_demo` → read durable history/catalog/lots → `forecast_demand(..., business_today(), 7)` → `purchase_plan` → reopen → reseed. Exit **0**; **630** synthetic history rows, **49** forecasts, **49** purchase-plan rows, all **Random Forest**, **90** recorded history days per ingredient, estimated virtual purchase cost **S/1284.90**. Assertions prove nonnegative suggestions, closing safety balances, unchanged operational lots/stock, restart persistence and idempotent seed. |
| Live browser smoke | Root operated the running local Streamlit app at `http://127.0.0.1:8501`: explicit welcome/demo choice, dashboard, purchase plan and RF chart; responsive viewport inspected. Root recorded one real demo sale (one Arroz con pollo portion, **S/16**). Durable service confirmed Pollo **18 → 17.78 kg**, Arroz **30 → 29.85 kg**, Cebolla **8 → 7.96 kg**, Aceite **8 → 7.98 L**; other balances unchanged. Reload retained sale, dashboard revenue **S/16.00**, stock value **S/722.87**. No stray `None` text. |
| Screenshot inspection | `output/restaurante-resumen.jpg` inspected by root and integration executor: legible demo label, Lima date, metrics, expiry table and persisted sale, with no visible clipping or overlap in the captured viewport. |
| Rollback boundary | Restore only previous `openspec/config.yaml` and clear task 4.4; remove this integration evidence artifact if reverting the integration unit. Preserve all application files and user/demo SQLite databases. |

## Testing capabilities persisted

`openspec/config.yaml` now records actual Python/Streamlit/SQLite architecture; workspace pytest command; forecast unit tests, SQLite service integration tests, simulated Streamlit AppTest UI coverage; Ruff and compileall commands. Automated browser E2E is explicitly false; manual browser smoke is separate. No coverage percentage or static type-check result is invented.

## Limits

This is a local single-administrator system. No public deployment, multi-user access control, live supplier purchase or full research evaluation is claimed. Demo data remain synthetic and separately persisted; isolated test/harness databases are temporary. Independent SDD verification must run after this implementation evidence.
