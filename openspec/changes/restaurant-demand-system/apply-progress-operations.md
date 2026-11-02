# Apply progress: persistence and restaurant operations

Status: complete for assigned tasks 1.1–1.4 and 2.1–2.5.
Mode: Standard (`strict_tdd: false`). Store: OpenSpec.
Authority: local workspace implementation under the project root; no PR or repository publication requested.

## Delivered behavior

- SQLite schema with foreign keys, WAL, immediate transactions and closed per-call connections.
- Ingredients, dishes and recipes; safe disabling; unit protection after movements; immutable sale-price and ingredient-consumption snapshots.
- Purchase lots, FIFO recipe sales, manual waste, idempotent expiry processing and payload-aware retry protection.
- Failed multi-ingredient sales leave inventory, history and request keys unchanged.
- America/Lima dates; future and out-of-order operational movements rejected.
- Explicit, atomic, one-time synthetic demo seeding, isolated from the own-restaurant filename and never overwriting an existing catalog.
- Finite numeric inputs bounded at 1,000,000,000 (positive operational quantities have a 0.000001 minimum) to protect calculated amounts and SQLite integer bindings.

## Work Unit Evidence

| Evidence | Exact result |
|---|---|
| Focused tests | `.venv/bin/python -m pytest tests/test_service.py -q` — exit 0, **27 passed in 0.78s** |
| Static checks | `.venv/bin/ruff check src/restaurante/db.py src/restaurante/service.py src/restaurante/seed.py src/restaurante/__init__.py tests/test_service.py pyproject.toml` — exit 0, **All checks passed!** |
| Runtime harness | Temporary SQLite database: create ingredient/recipe → receive 2 kg → sell 3 portions consuming 0.6 kg → record 0.1 kg waste → reopen. Exit 0; stock **1.300 kg**, sales **S/45**, durable purchase/sale/waste counts **1/1/1**. |
| Packaging | `UV_CACHE_DIR=/private/tmp/seminario-uv-cache uv pip install --python .venv/bin/python --no-deps -e .` — exit 0; editable `restaurante-predictivo==0.1.0` installed. |
| Rollback boundary | Remove `src/restaurante/{__init__,db,service,seed}.py`, `tests/test_service.py`, `pyproject.toml` and `.gitignore` before adopting dependent modules. Preserve existing user SQLite files; this work does not migrate external data. |

## Notes for integration

`stock(as_of)` reports eligible and expired physical balances without mutating history. `expire_stock(as_of)` explicitly processes remaining expired lots into auditable `Vencimiento` waste exactly once. The UI must expose that operation.

Returned empty dataframes retain query-defined columns. All persisted operational inputs use canonical ISO dates. Idempotent replay returns the original operation id even after subsequent movements.

PR review-budget planning is a future publication concern; this unit remains an uncommitted local implementation slice. No maintainer exception or PR chain decision is fabricated.

Authored line count: 821 across schema/service/seed/package/config/tests. The complete operations slice exceeds 400 lines because transactional inventory, validation, audit history and behavioral tests form one coherent local foundation; no code was compressed to fit a future PR budget.
