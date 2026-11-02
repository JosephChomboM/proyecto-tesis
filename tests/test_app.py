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
