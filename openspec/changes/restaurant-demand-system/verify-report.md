```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:34772598365f8b85c10aa1eedc9a714b1a09fe3696f9f119ca6872bfa4d42ad7
verdict: pass
blockers: 0
critical_findings: 0
requirements: 9/9
scenarios: 15/15
test_command: .venv/bin/python -m pytest -q tests /private/tmp/seminario-verification/test_acceptance_probe.py
test_exit_code: 0
test_output_hash: sha256:4310623eb95c7194a00d414aa00563890968c3728e763abfe6da4f9bf8046b02
build_command: .venv/bin/ruff check . && .venv/bin/python -m compileall -q app.py src/restaurante
build_exit_code: 0
build_output_hash: sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18
```

## Verification Report

**Change**: restaurant-demand-system  
**Date**: 2026-11-01 (America/Lima)  
**Mode**: Standard; `strict_tdd: false` is preserved.  
**Scope**: Local single-administrator application, against all four current capability specifications. This is independent requirements/runtime verification, not a scientific validation of thesis hypotheses.

### Completeness

| Metric | Value |
|---|---|
| Tasks total / complete / incomplete | 15 / 15 / 0 |
| Requirements counted from actual `### Requirement:` headings | 9 |
| Scenarios counted from actual `#### Scenario:` headings | 15 |
| Complete source artifacts retrieved | Proposal, exploration, four specs, design, tasks, four apply-progress artifacts, config, source, tests, README and traceability |
| Implementation files changed by verification | None |

Full verification began only after all task checkboxes were complete and the orchestrator confirmed the final source/config tree was frozen. The proposal's unchecked success-criteria bullets are original acceptance criteria, not pending implementation tasks; their behavior is verified below.

### Build & Tests Execution

The exact commands, exit codes and SHA-256 hashes of their combined stdout/stderr bytes are in the envelope. Commands were executed independently by this phase from the workspace root.

- Workspace suite: **57 passed** (27 service, 25 forecast, 5 Streamlit AppTest cases).
- Additional temporary acceptance tests: **2 passed**, exercising real Streamlit CSV payloads after a UI purchase/sale and an actionable UI validation error.
- Final combined execution: **59 passed in 3.87s**, exit **0**.
- Ruff: **All checks passed!**, exit **0**.
- `compileall`: exit **0**, no diagnostics. This establishes compilation, not a deployment or distribution-package build.
- Coverage percentage and static type checking: not configured; no claim made. The configured coverage threshold is zero.
- Automated real-browser E2E: not available; AppTest exercises actual Streamlit scripts with temporary databases. Manual browser evidence is separately attributed below.

Exact final test output:

```text
...........................................................              [100%]
59 passed in 3.87s
```

Exact final build output:

```text
All checks passed!
```

### Spec Compliance Matrix

All named repository tests ran and passed in the final command. Acceptance probes are reproduced in the appendix and also passed in that command.

| Requirement | Scenario | Passing runtime coverage | Result |
|---|---|---|---|
| CAT-1 Editable catalog | Valid recipe | `tests/test_service.py::test_catalog_recipe_and_restart_persistence`; `tests/test_app.py::test_catalog_can_create_recipe_and_toggle_active` | COMPLIANT |
| CAT-1 Editable catalog | Invalid amount | `test_invalid_catalog_numeric_values_leave_no_changes` (negative/nonfinite/extreme values); `test_invalid_recipe_is_atomic`; `test_invalid_ingredient_dimensions`; UI `test_invalid_catalog_error_runtime` confirms actionable error without mutation | COMPLIANT |
| CAT-2 Historical safety | Disabled dish | `tests/test_service.py::test_recipe_price_edits_and_disable_preserve_history`; `tests/test_app.py::test_catalog_can_create_recipe_and_toggle_active` | COMPLIANT |
| OPS-1 Receipts and waste | Purchase receipt | `tests/test_service.py::test_catalog_recipe_and_restart_persistence`; acceptance `test_completed_workflow_export_runtime` | COMPLIANT |
| OPS-1 Receipts and waste | Expiration | `tests/test_service.py::test_expired_stock_cannot_sell_and_expiration_audited_once`; `test_same_day_expiry_is_eligible` | COMPLIANT |
| OPS-2 Atomic sales | FIFO sale | `tests/test_service.py::test_fifo_sale_uses_older_lot_and_survives_restart` | COMPLIANT |
| OPS-2 Atomic sales | Insufficient ingredient | `tests/test_service.py::test_insufficient_one_ingredient_rolls_back_entire_sale` | COMPLIANT |
| OPS-3 Idempotent writes | Retry | `tests/test_service.py::test_purchase_sale_and_waste_idempotency_and_conflicts` covers all three operation kinds | COMPLIANT |
| OPS-3 Idempotent writes | Conflicting retry | `tests/test_service.py::test_purchase_sale_and_waste_idempotency_and_conflicts` | COMPLIANT |
| PLAN-1 Honest forecasts | Empty history | `tests/test_forecast.py::test_empty_history_is_explicit_zero_placeholder`; `tests/test_app.py::test_empty_history_forecast_renders_without_false_accuracy` | COMPLIANT |
| PLAN-1 Honest forecasts | Future observation changed | `tests/test_forecast.py::test_random_forest_uses_only_prior_data_and_is_deterministic`; `test_no_cross_ingredient_demand_leakage` | COMPLIANT |
| PLAN-2 Purchase suggestions | Stock allocated once | `tests/test_forecast.py::test_stock_allocated_once_with_carryover_and_pack_rounding`; `test_virtual_receipts_expire_and_safety_is_not_consumed` | COMPLIANT |
| PLAN-2 Purchase suggestions | Expiring stock | `tests/test_forecast.py::test_expiring_stock_and_same_day_expiry`; `test_future_receipt_is_not_available_early`; `test_fifo_planning_preserves_later_lot_when_old_lot_consumed` | COMPLIANT |
| UI-1 Isolated modes | Mode switch | `tests/test_app.py::test_demo_and_own_restaurant_are_isolated`; `test_startup_requires_explicit_mode`; `tests/test_service.py::test_demo_is_explicit_atomic_and_idempotent` | COMPLIANT |
| UI-2 Usable operations | Completed workflow | `tests/test_app.py::test_purchase_sale_and_dashboard_persist`; acceptance `test_completed_workflow_export_runtime` confirms committed UI purchase/sale, dashboard, stock CSV, sales CSV and reopened SQLite values | COMPLIANT |

**Compliance summary**: **9/9 requirements, 15/15 scenarios compliant**.

### Correctness (Static Evidence)

| Requirement group | Implementation evidence | Assessment |
|---|---|---|
| CAT-1/2 | `service.py` validates finite bounded numeric quantities, positive recipes, identifiers and text; disabling preserves references and sales snapshots | Implemented |
| OPS-1 | Dated purchase lots, explicit auditable expiration processing, costed FIFO waste and eligible-stock filtering | Implemented |
| OPS-2 | `record_sale` checks every dish/ingredient and all aggregate requirements before writes; SQLite immediate transaction rolls back any failure; price/name/consumption snapshots persist | Implemented |
| OPS-3 | Unique request key plus canonical payload hash and kind; replay returns original id, conflict rejects within transaction | Implemented |
| PLAN-1 | Observations filtered strictly before origin; per-ingredient models, lagged features and deterministic recursive RF; explicit zero/mean/seasonal fallbacks | Implemented |
| PLAN-2 | Independent chronological virtual lot ledger; same-day expiry, date-qualified receipts, FIFO, safety targets, pack rounding and carryover; input data copied | Implemented |
| UI-1/2 | Explicit mode choice, two database paths, one-time demo seeding, Spanish operational forms, CSV exports and `ZoneInfo('America/Lima')` business dates | Implemented |

### Coherence (Design)

| Decision | Followed? | Evidence |
|---|---|---|
| Streamlit presentation over Python service / SQLite | Yes | UI calls `RestaurantService`; parameterized statements, foreign keys, per-call connection cleanup and immediate transactions |
| Separate demo and own data | Yes | No database before explicit choice; separate files; seed marker and separate synthetic-demand table |
| Immutable historical consumption | Yes | Sales store recipe consumption and price snapshots; recipe/price edits cannot recalculate old demand |
| RF with honest fallbacks | Yes | 56 observed-day requirement; visible method/limitations, no invented accuracy |
| Virtual purchase planning without ordering | Yes | Planning function never calls persistence or supplier interfaces; UI explicitly states recommendations do not register purchases |
| Local trusted administrator | Yes | Loopback bind in Streamlit config; no authentication/public-hosting claim |
| Documented limitations | Yes | README and traceability distinguish software completion from calibration, advanced model comparison, inventory-policy experiments, expert/Aiken and SUS evidence |

The actual package is `src/restaurante/`, consistently reflected in the finalized design, proposal and exploration. The interface submits one dish with multiple portions per sale; the service supports multi-line transactions. No specification requires a multi-dish UI cart.

### Additional Runtime and Browser Evidence

The independent temporary CSV test used an empty own-restaurant database, configured a 0.2 kg recipe, received 2 kg through the application and sold three portions through the application. `stock.csv` contained `Disponible=1.4`; `ventas.csv` contained `Total (S/)=45` and `Porciones=3`; dashboard displayed `S/ 45.00`; reopening SQLite retained 1.4 kg. A separate UI test submitted an empty ingredient name and observed `Nombre: completa...` without an exception or catalog mutation. Numeric-invalid submissions are covered at the service boundary; Streamlit numeric controls also constrain ordinary negative input.

Separately, the root orchestrator and integration executor report a live browser smoke at `http://127.0.0.1:8501`: welcome choice, demo dashboard, RF chart, purchase plan, responsive view and a one-portion Arroz con pollo sale of S/16. Their service inspection found Pollo 18→17.78 kg, Arroz 30→29.85 kg, Cebolla 8→7.96 kg and Aceite 8→7.98 L; reload preserved S/16 revenue and S/722.87 estimated stock value. Screenshot: `output/restaurante-resumen.jpg`. These are attributed manual observations, not an independently executed browser E2E suite by this verifier; requirement compliance above rests on independently passed tests.

### Issues Found

**CRITICAL**: None.  
**WARNING**: None within the declared local operational scope.  
**SUGGESTION**: Retain the acceptance probe as a permanent regression test if export behavior evolves. Its exact temporary source is preserved below for reproducibility.

### Verdict

**PASS**. All 15 implementation tasks are complete; independent runtime checks cover all 15 specified scenarios and all 9 requirements, and lint/compilation pass. This verdict covers the implemented local restaurant system. It does not certify model accuracy, causal inventory improvement, thesis calibration, three complete 2024–2025 research profiles, RF/XGBoost/LSTM comparison, Aiken/expert results, SUS scores, multi-user security or production deployment.

### Evidence Identity

`evidence_revision` hashes the UTF-8 manifest reproduced below, including its final newline. Each entry is a relative workspace path (or an absolute temporary probe/output path), one space, and the lowercase SHA-256 of its exact bytes. The report itself is excluded to avoid a circular digest. Database contents and transient bytecode are excluded; all verification tests use temporary databases. Canonical output hashes refer only to final command output, not this report's prose.

```text
.streamlit/config.toml a430e934bb319b83ccb3d90360bc0067f3d6196215ba30d65d254c774edfd0a2
README.md 4b95819cb81668b33ef9b8678885762aa76d285fba6967a1e1f2ea95eab77f26
app.py 8219beb905acbeec7c85708c7f06c1e0a0a991e3608f9bc25730e5fa6bb36bfb
docs/traceability.md 0df1359bca4ec05f2da98bef38a152cfd250fa6792afc4d3ffb508400a0ee766
openspec/changes/restaurant-demand-system/apply-progress-forecast.md 31f5a60d3a351c75b64befd9b1f0efdc50cb16019c60e21bef3d26ca44e08d28
openspec/changes/restaurant-demand-system/apply-progress-integration.md 0569944fe872c5ea4a4dcc9d72bd8027b4035b9f4e7dd491b0ba718afd714f9a
openspec/changes/restaurant-demand-system/apply-progress-interface.md 5b9b16496add2343b220ecfaa1b57b5ed61908003d239467a57ae62c447bb10c
openspec/changes/restaurant-demand-system/apply-progress-operations.md 7e5452dc3812c996a6cfa3edb8039dfbd386c4f2c750b32e4e51f5e8ca44b432
openspec/changes/restaurant-demand-system/design.md 1c31eab3cf3bbe29f95f2fb05bf798bddf9a05bf465f35159ece8fdd1e62803a
openspec/changes/restaurant-demand-system/exploration.md 80cfeb00ad6f5aef0be09abb90963244cd47a32bd7cd0f55a3a71d4f4ac04ad4
openspec/changes/restaurant-demand-system/proposal.md 5ca8740893941a956cce3971465dd5b063b1c1568d7ab9f8c0f8bddcddfb4d46
openspec/changes/restaurant-demand-system/specs/inventory-planning/spec.md 6bb6c54df627f400fb30fe7b0d0fdd3e586fc80344d30711bdba782d369331e9
openspec/changes/restaurant-demand-system/specs/restaurant-catalog/spec.md 53983594f45205c6c782358323024c21d5edf45d297c16fde82c035341c87dd5
openspec/changes/restaurant-demand-system/specs/restaurant-operations/spec.md 18a8ca3f4bc763ece23c10dcf12f605510fe72e507d7ff899f1cddf3dae75739
openspec/changes/restaurant-demand-system/specs/restaurant-prototype/spec.md c7295801404be4c432a6c941ad888441fe8847cabdff8278fd91b0e784bdbe2a
openspec/changes/restaurant-demand-system/tasks.md 8af296aee3d7390b82516201255037f794c4230fad224946bc6d182cf86e2fb2
openspec/config.yaml 6c091ba35ad1d0ace5f111bb2d9969d1d7f7661db1f80f6d1295027a37b8e268
pyproject.toml edaa27e59a45303c894a3839e18071aa284ec03dc605535bc53f2c547e9361bb
src/restaurante/__init__.py eea63313d4fcd2aa28e6e7915e853836f8ac6d8da4ab94a05d30f7cbc7267f64
src/restaurante/db.py 2029b0999be74fb383ed850c6baff796ea23e666cc551eb027d55d4d97d7b275
src/restaurante/forecast.py 5a86043a6cca98c9cbc807a062c1ad8250313358e98ce8283b09de9975288100
src/restaurante/seed.py d0a03ac24bc5e99f9756b1741310d90cc33fd5ceda62881c878e8fd44a436563
src/restaurante/service.py 5569ed5ce8f16d86ff531d7a339667c79f29c5c3cc4d516a01fedc86f67ea00d
tests/test_app.py 8720e1f9d7fccd5681c97ce9a4b60f8b961b7dde361bd75f19dd21ca9abc22fb
tests/test_forecast.py 6bba7d0676bfd890a61560215a25497b1ba3620635f40b4a37c4312c020bd435
tests/test_service.py 93359038f1047e9c0035e72daea5a3a0be6db2c8f55a61ca1b677eabf8113638
/private/tmp/seminario-verification/build-final.txt 82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18
/private/tmp/seminario-verification/test-final.txt 4310623eb95c7194a00d414aa00563890968c3728e763abfe6da4f9bf8046b02
/private/tmp/seminario-verification/test_acceptance_probe.py 7dc5b7df3534589ff4a75a9c72123fbfb2cf71681962a8ff3600b21abd2474c0
```

### Temporary Acceptance Probe Source

Recreate at the path named in the final test command if the temporary directory is removed.

```python
import io
from pathlib import Path
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from restaurante.service import RestaurantService, business_today

APP=Path('/Users/josephchombo/Projects/seminario/app.py')
def label(elements,name):
    return next(e for e in elements if e.label==name)
def nav(app,page):
    label(app.radio,'Tu operación').set_value(page).run()
    assert not app.exception

def test_completed_workflow_export_runtime(tmp_path,monkeypatch):
    monkeypatch.setenv('RESTAURANTE_DATA_DIR',str(tmp_path))
    captured={}
    original=st.download_button
    def download(*args,**kwargs):
        captured[kwargs['file_name']]=args[1]
        return original(*args,**kwargs)
    monkeypatch.setattr(st,'download_button',download)
    service=RestaurantService(tmp_path/'restaurant.sqlite3')
    rice=service.save_ingredient('Arroz','kg',4,1,20,0)
    dish=service.save_dish('Menú',15)
    service.set_recipe(dish,{rice:0.2})
    app=AppTest.from_file(str(APP),default_timeout=30).run()
    label(app.button,'Comenzar mi restaurante').click().run()
    nav(app,'Compras')
    label(app.number_input,'Cantidad recibida (kg)').set_value(2.0)
    label(app.button,'Registrar compra').click().run()
    assert not app.exception
    nav(app,'Ventas')
    label(app.number_input,'Porciones vendidas').set_value(3)
    label(app.button,'Registrar venta').click().run()
    assert not app.exception
    nav(app,'Stock y mermas')
    stock=pd.read_csv(io.BytesIO(captured['stock.csv']))
    assert stock.iloc[0]['Disponible']==pytest.approx(1.4)
    nav(app,'Resumen')
    assert label(app.metric,'Ventas de hoy').value=='S/ 45.00'
    sales=pd.read_csv(io.BytesIO(captured['ventas.csv']))
    assert sales.iloc[0]['Total (S/)']==45
    assert sales.iloc[0]['Porciones']==3
    reopened=RestaurantService(tmp_path/'restaurant.sqlite3')
    assert reopened.stock(business_today()).iloc[0]['available']==pytest.approx(1.4)
    print('CSV runtime: stock Disponible=1.4; sales Total=45, Porciones=3; dashboard S/45; reopen consistent.')

def test_invalid_catalog_error_runtime(tmp_path,monkeypatch):
    monkeypatch.setenv('RESTAURANTE_DATA_DIR',str(tmp_path))
    app=AppTest.from_file(str(APP),default_timeout=30).run()
    label(app.button,'Comenzar mi restaurante').click().run()
    nav(app,'Catálogo')
    label(app.button,'Guardar insumo').click().run()
    assert not app.exception
    assert any('Nombre: completa' in e.value for e in app.error)
    assert RestaurantService(tmp_path/'restaurant.sqlite3').ingredients().empty
```
