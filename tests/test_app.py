"""Administrator workflows against an isolated local application."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from restaurante.service import RestaurantService, business_today

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("RESTAURANTE_DATA_DIR", str(tmp_path))
    return AppTest.from_file(str(APP), default_timeout=30)


def by_label(elements, label):
    return next(element for element in elements if element.label == label)


def navigate(app, page):
    by_label(app.radio, "Tu operación").set_value(page).run()
    assert not app.exception
    assert all(element.value != "None" for element in app.markdown)


def test_startup_requires_explicit_mode(app, tmp_path):
    app.run()
    assert not app.exception
    assert not (tmp_path / "restaurant.sqlite3").exists()
    assert not (tmp_path / "demo.sqlite3").exists()
    by_label(app.button, "Comenzar mi restaurante").click().run()
    assert not app.exception
    assert (tmp_path / "restaurant.sqlite3").exists()
    assert not (tmp_path / "demo.sqlite3").exists()
    assert RestaurantService(tmp_path / "restaurant.sqlite3").ingredients().empty
    navigate(app, "Plan de compras")
    assert any("Registra tus insumos" in message.value for message in app.info)


def test_demo_and_own_restaurant_are_isolated(app, tmp_path):
    app.run()
    by_label(app.button, "Explorar demostración").click().run()
    assert not app.exception
    assert not RestaurantService(tmp_path / "demo.sqlite3").ingredients().empty
    by_label(app.selectbox, "Espacio de trabajo").select("Mi restaurante").run()
    assert not app.exception
    assert RestaurantService(tmp_path / "restaurant.sqlite3").ingredients().empty
    navigate(app, "Catálogo")
    assert not app.exception
    by_label(app.selectbox, "Espacio de trabajo").select("Demostración").run()
    assert not app.exception
    assert not RestaurantService(tmp_path / "demo.sqlite3").ingredients().empty


def test_purchase_sale_and_dashboard_persist(app, tmp_path):
    service = RestaurantService(tmp_path / "restaurant.sqlite3")
    ingredient = service.save_ingredient("Arroz", "kg", 4, 1, 20, 1)
    dish = service.save_dish("Arroz de prueba", 12)
    service.set_recipe(dish, {ingredient: 0.25})
    app.run()
    by_label(app.button, "Comenzar mi restaurante").click().run()
    navigate(app, "Compras")
    by_label(app.number_input, "Cantidad recibida (kg)").set_value(5.0)
    by_label(app.button, "Registrar compra").click().run()
    assert not app.exception
    assert service.stock(business_today()).iloc[0]["available"] == pytest.approx(5)
    assert len(service.purchases()) == 1
    navigate(app, "Ventas")
    by_label(app.number_input, "Porciones vendidas").set_value(2)
    by_label(app.button, "Registrar venta").click().run()
    assert not app.exception
    assert len(service.sales()) == 1
    assert service.stock(business_today()).iloc[0]["available"] == pytest.approx(4.5)
    navigate(app, "Resumen")
    assert by_label(app.metric, "Ventas de hoy").value == "S/ 24.00"
    navigate(app, "Plan de compras")
    assert not app.exception
    assert any("Método utilizado:" in message.value for message in app.caption)


def test_empty_history_forecast_renders_without_false_accuracy(app, tmp_path):
    service = RestaurantService(tmp_path / "restaurant.sqlite3")
    service.save_ingredient("Papa", "kg", 3, 5, 7, 2)
    app.run()
    by_label(app.button, "Comenzar mi restaurante").click().run()
    navigate(app, "Plan de compras")
    assert any("Aún no hay historial" in warning.value for warning in app.warning)
    assert not app.exception


def test_catalog_can_create_recipe_and_toggle_active(app, tmp_path):
    app.run()
    by_label(app.button, "Comenzar mi restaurante").click().run()
    navigate(app, "Catálogo")
    by_label(app.text_input, "Nombre del insumo").set_value("Pollo")
    by_label(app.number_input, "Costo de referencia por unidad (S/)").set_value(10.0)
    by_label(app.button, "Guardar insumo").click().run()
    assert not app.exception
    by_label(app.text_input, "Nombre del plato").set_value("Pollo al horno")
    by_label(app.number_input, "Precio de venta (S/)").set_value(18.0)
    by_label(app.button, "Guardar plato").click().run()
    assert not app.exception
    by_label(app.number_input, "Pollo (kg)").set_value(0.4)
    by_label(app.button, "Guardar receta").click().run()
    assert not app.exception
    service = RestaurantService(tmp_path / "restaurant.sqlite3")
    dish_id = int(service.dishes().iloc[0]["id"])
    assert service.recipe(dish_id).iloc[0]["quantity"] == pytest.approx(0.4)
    by_label(app.selectbox, "Plato a editar").select(dish_id).run()
    by_label(app.checkbox, "Plato activo").uncheck()
    by_label(app.button, "Guardar plato").click().run()
    assert not app.exception
    assert service.dishes().empty
    assert len(service.dishes(include_inactive=True)) == 1
    assert not service.recipe(dish_id).empty


def test_presentation_purchase_converts_quantity_and_unit_cost(app, tmp_path):
    service = RestaurantService(tmp_path / "restaurant.sqlite3")
    service.save_ingredient("Arroz", "kg", 4, 50, 90, 1)
    app.run()
    by_label(app.button, "Comenzar mi restaurante").click().run()
    navigate(app, "Compras")
    by_label(app.radio, "Ingresar cantidad como").set_value("Presentaciones").run()
    by_label(app.number_input, "Número de presentaciones").set_value(2.0)
    by_label(app.number_input, "Costo por presentación (S/)").set_value(180.0)
    by_label(app.button, "Registrar compra").click().run()
    assert not app.exception
    assert service.purchases().quantity.iloc[0] == 100
    assert service.purchases().unit_cost.iloc[0] == 3.6
    assert service.purchases().total.iloc[0] == 360


def test_closure_requires_confirmation_and_enables_complete_history(app, tmp_path):
    service = RestaurantService(tmp_path / "restaurant.sqlite3")
    service.save_ingredient("Papa", "kg", 3, 5, 7, 0)
    app.run()
    by_label(app.button, "Comenzar mi restaurante").click().run()
    navigate(app, "Cierre diario")
    by_label(app.button, "Cerrar jornada").click().run()
    assert service.closures().empty
    by_label(app.checkbox, "He revisado los registros y confirmo el cierre").check()
    by_label(app.button, "Cerrar jornada").click().run()
    assert not app.exception
    assert len(service.closures()) == 1
    assert service.forecast_history().quantity.tolist() == [0]
    navigate(app, "Plan de compras")
    assert not app.exception


def test_demo_evaluation_renders_metrics(app):
    app.run()
    by_label(app.button, "Explorar demostración").click().run()
    navigate(app, "Plan de compras")
    by_label(app.button, "Evaluar con historial disponible").click().run(timeout=60)
    assert not app.exception
    assert any("WAPE (%)" in frame.value.columns for frame in app.dataframe)


def test_dashboard_quick_action_navigates_to_purchase_form(app):
    app.run()
    by_label(app.button, "Explorar demostración").click().run()
    by_label(app.button, "Nueva compra").click().run()
    assert not app.exception
    assert by_label(app.radio, "Tu operación").value == "Compras"
    assert by_label(app.button, "Registrar compra")


def test_inventory_search_filters_visible_table(app, tmp_path):
    service = RestaurantService(tmp_path / "restaurant.sqlite3")
    service.save_ingredient("Arroz", "kg", 4, 50, 90, 1)
    service.save_ingredient("Pollo", "kg", 12, 1, 2, 1)
    app.run()
    by_label(app.button, "Comenzar mi restaurante").click().run()
    navigate(app, "Stock y mermas")
    by_label(app.text_input, "Buscar insumo").set_value("ARROZ").run()
    assert not app.exception
    stock_table = next(frame.value for frame in app.dataframe if "Disponible" in frame.value.columns)
    assert stock_table["Nombre"].tolist() == ["Arroz"]


def test_report_page_has_period_metrics_and_clear_empty_state(app):
    app.run()
    by_label(app.button, "Comenzar mi restaurante").click().run()
    by_label(app.button, "Ver reportes por fecha").click().run()
    assert not app.exception
    assert by_label(app.radio, "Tu operación").value == "Reportes"
    assert by_label(app.metric, "Ventas registradas").value == "S/ 0.00"
    assert any("podrían estar incompletos" in message.value for message in app.warning)


def test_research_generates_separate_dataset_and_preserves_inventory(app, tmp_path):
    app.run()
    by_label(app.button, "Explorar demostración").click().run()
    service = RestaurantService(tmp_path / "demo.sqlite3")
    before = service.lots().copy()
    navigate(app, "Investigación")
    by_label(app.button, "Generar dataset sintético").click().run(timeout=60)
    assert not app.exception
    assert by_label(app.metric, "Días por serie").value == "731"
    assert any(button.label == "Descargar dataset y configuración (ZIP)" for button in app.get("download_button"))
    import pandas as pd
    pd.testing.assert_frame_equal(before, service.lots())


def test_public_research_does_not_offer_training(app, monkeypatch):
    monkeypatch.setenv("RESTAURANTE_PUBLIC_DEMO", "true")
    app.run()
    by_label(app.button, "Explorar demostración").click().run()
    navigate(app, "Investigación")
    assert not any(button.label == "Entrenar, evaluar y simular compras" for button in app.button)
    assert any("Render gratuito" in message.value for message in app.info)


def test_research_example_reports_open_without_training(app):
    app.run()
    by_label(app.button, "Preparar datos para la tesis").click().run()
    assert not app.exception
    assert by_label(app.radio, "Tu operación").value == "Investigación"
    by_label(app.button, "Ver experimento de ejemplo").click().run()
    assert not app.exception
    assert not app.error
    assert by_label(app.metric, "Merma con pronóstico")


def test_plan_registers_exceptional_closure_and_explains_context(app, tmp_path):
    from datetime import timedelta
    service = RestaurantService(tmp_path / "restaurant.sqlite3")
    service.save_ingredient("Pollo", "kg", 10, 1, 2, 1)
    app.run()
    by_label(app.button, "Comenzar mi restaurante").click().run()
    navigate(app, "Plan de compras")
    by_label(app.selectbox, "Tipo de evento especial").select("closure")
    by_label(app.text_input, "Descripción del evento").set_value("Mantenimiento de cocina")
    by_label(app.button, "Guardar evento").click().run()
    assert not app.exception and not app.error
    assert service.events().iloc[0]["name"] == "Mantenimiento de cocina"
    context = next(frame.value for frame in app.dataframe if "Contexto del día" in frame.value
                   and "¿Es feriado?" in frame.value)
    assert context.iloc[0]["Contexto del día"] == "Mantenimiento de cocina"
    assert not bool(context.iloc[0]["Día de atención"])
    assert service.sales().empty and service.purchases().empty
    assert service.events().iloc[0].day == (business_today()+timedelta(days=1)).isoformat()
    by_label(app.button, "Retirar evento").click().run()
    assert not app.exception
    assert service.events().empty
    assert len(service.events(include_history=True)) == 2
