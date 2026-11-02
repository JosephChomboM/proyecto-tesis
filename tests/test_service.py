from datetime import timedelta

import pandas as pd
import pytest

from restaurante import DomainError, RestaurantService, business_today
from restaurante.seed import seed_demo


@pytest.fixture
def service(tmp_path):
    return RestaurantService(tmp_path / "test.sqlite3")


def ingredient(service, name="Arroz", unit="kg"):
    return service.save_ingredient(name, unit, 4, 1, 30, 1)


def receipt(service, ingredient_id, quantity, key="p1", day=None, expiry=None, cost=4):
    day = day or business_today()
    return service.receive_purchase(ingredient_id, quantity, cost, day,
                                    expiry or day + timedelta(days=30), key)


def setup_dish(service, requirements=None):
    rice = ingredient(service)
    dish = service.save_dish("Menú", 15)
    service.set_recipe(dish, requirements or {rice: 0.2})
    return rice, dish


def test_catalog_recipe_and_restart_persistence(service):
    rice, dish = setup_dish(service)
    reopened = RestaurantService(service.db_path)
    assert reopened.ingredients().iloc[0]["name"] == "Arroz"
    assert reopened.recipe(dish).iloc[0].to_dict() == {"ingredient_id": rice, "quantity": 0.2}
    receipt(reopened, rice, 3)
    assert RestaurantService(service.db_path).stock(business_today()).iloc[0]["available"] == 3
    assert RestaurantService(service.db_path).purchases().iloc[0]["total"] == 12


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), -float("inf"), True, 1e308])
def test_invalid_catalog_numeric_values_leave_no_changes(service, value):
    with pytest.raises(DomainError):
        service.save_ingredient("Inválido", "kg", value, 1, 3, 0)
    assert service.ingredients().empty


@pytest.mark.parametrize("field,value", [("pack_size", 0), ("shelf_life_days", 0),
                                         ("shelf_life_days", 1.5), ("safety_stock", -1)])
def test_invalid_ingredient_dimensions(service, field, value):
    fields = dict(name="Arroz", unit="kg", cost=4, pack_size=1, shelf_life_days=30, safety_stock=0)
    fields[field] = value
    with pytest.raises(DomainError):
        service.save_ingredient(**fields)
    assert service.ingredients().empty


def test_invalid_recipe_is_atomic(service):
    rice, dish = setup_dish(service)
    with pytest.raises(DomainError):
        service.set_recipe(dish, {rice: -2})
    assert service.recipe(dish).iloc[0]["quantity"] == 0.2


def test_subprecision_recipe_is_rejected_instead_of_selling_without_consumption(service):
    rice, dish = setup_dish(service)
    with pytest.raises(DomainError, match="mínima"):
        service.set_recipe(dish, {rice: 1e-12})
    assert service.recipe(dish).iloc[0]["quantity"] == 0.2


def test_fifo_sale_uses_older_lot_and_survives_restart(service):
    rice, dish = setup_dish(service)
    today = business_today()
    receipt(service, rice, 0.3, "old", today - timedelta(days=1))
    receipt(service, rice, 1, "new", today)
    sale_id = service.record_sale({dish: 2}, today, "s1")
    lots = service.lots()
    assert lots.iloc[0]["remaining"] == 0
    assert lots.iloc[1]["remaining"] == pytest.approx(0.9)
    reopened = RestaurantService(service.db_path)
    assert reopened.sales().iloc[0]["id"] == sale_id
    assert reopened.sales().iloc[0]["total"] == 30
    assert reopened.demand_history().iloc[0]["quantity"] == pytest.approx(0.4)


def test_insufficient_one_ingredient_rolls_back_entire_sale(service):
    rice, dish = setup_dish(service)
    chicken = ingredient(service, "Pollo")
    service.set_recipe(dish, {rice: 0.2, chicken: 0.25})
    receipt(service, rice, 10)
    receipt(service, chicken, 0.1, "p2")
    before = service.lots()
    with pytest.raises(DomainError, match="Stock insuficiente"):
        service.record_sale({dish: 1}, business_today(), "failed")
    pd.testing.assert_frame_equal(service.lots(), before)
    assert service.sales().empty
    assert service.demand_history().empty


def test_expired_stock_cannot_sell_and_expiration_audited_once(service):
    rice, dish = setup_dish(service)
    today = business_today()
    receipt(service, rice, 2, day=today - timedelta(days=3), expiry=today - timedelta(days=1))
    stock = service.stock(today).iloc[0]
    assert stock["available"] == 0
    assert stock["expired"] == 2
    with pytest.raises(DomainError):
        service.record_sale({dish: 1}, today, "s1")
    assert service.expire_stock(today) == 1
    assert service.expire_stock(today) == 0
    waste = service.waste().iloc[0]
    assert waste["quantity"] == 2
    assert waste["cost"] == 8
    assert waste["reason"] == "Vencimiento"
    assert service.lots().iloc[0]["remaining"] == 0


def test_same_day_expiry_is_eligible(service):
    rice, dish = setup_dish(service)
    receipt(service, rice, 1, expiry=business_today())
    service.record_sale({dish: 1}, business_today(), "s1")
    assert service.stock(business_today()).iloc[0]["available"] == pytest.approx(0.8)


def test_purchase_sale_and_waste_idempotency_and_conflicts(service):
    rice, dish = setup_dish(service)
    today = business_today()
    assert receipt(service, rice, 2, "p1") == receipt(service, rice, 2, "p1")
    with pytest.raises(DomainError, match="otros datos"):
        receipt(service, rice, 3, "p1")
    sale_id = service.record_sale({dish: 1}, today, "s1")
    assert service.record_sale({dish: 1}, today, "s1") == sale_id
    with pytest.raises(DomainError):
        service.record_sale({dish: 2}, today, "s1")
    waste_id = service.record_waste(rice, 0.3, "Deterioro", today, "w1")
    assert service.record_waste(rice, 0.3, "Deterioro", today, "w1") == waste_id
    with pytest.raises(DomainError):
        service.record_waste(rice, 0.4, "Deterioro", today, "w1")
    assert len(service.purchases()) == len(service.sales()) == len(service.waste()) == 1
    assert service.stock(today).iloc[0]["available"] == pytest.approx(1.5)


def test_recipe_price_edits_and_disable_preserve_history(service):
    rice, dish = setup_dish(service)
    receipt(service, rice, 2)
    service.record_sale({dish: 1}, business_today(), "s1")
    service.set_recipe(dish, {rice: 0.8})
    service.save_dish("Nuevo nombre", 30, dish)
    service.set_dish_active(dish, False)
    assert service.sales().iloc[0]["total"] == 15
    assert service.demand_history().iloc[0]["quantity"] == 0.2
    with pytest.raises(DomainError, match="desactivado"):
        service.record_sale({dish: 1}, business_today(), "s2")
    assert service.dishes().empty
    assert len(service.dishes(True)) == 1


def test_unit_changes_after_stock_and_inactive_ingredient_sales_rejected(service):
    rice, dish = setup_dish(service)
    receipt(service, rice, 2)
    with pytest.raises(DomainError, match="unidad"):
        service.save_ingredient("Arroz", "g", 4, 1, 30, 1, rice)
    service.set_ingredient_active(rice, False)
    with pytest.raises(DomainError):
        service.record_sale({dish: 1}, business_today(), "s1")
    assert len(service.ingredients(True)) == 1
    assert service.ingredients().empty
    assert service.stock(business_today()).iloc[0]["available"] == 2


def test_no_recipe_or_fractional_portion_rejected(service):
    dish = service.save_dish("Sin receta", 10)
    with pytest.raises(DomainError, match="receta"):
        service.record_sale({dish: 1}, business_today(), "s1")
    with pytest.raises(DomainError, match="entero"):
        service.record_sale({dish: 1.5}, business_today(), "s2")


def test_huge_portions_and_purchase_are_rejected_without_sqlite_overflow(service):
    rice, dish = setup_dish(service)
    with pytest.raises(DomainError, match="máximo"):
        receipt(service, rice, 1e308)
    with pytest.raises(DomainError, match="máximo"):
        service.record_sale({dish: 10**30}, business_today(), "huge")
    assert service.sales().empty
    assert service.purchases().empty


def test_catalog_accepts_dataframe_integer_ids(service):
    rice, dish = setup_dish(service)
    ingredient_id = service.ingredients().iloc[0]["id"]
    dish_id = service.dishes().iloc[0]["id"]
    service.save_ingredient("Arroz editado", "kg", 5, 1, 30, 1, ingredient_id)
    service.save_dish("Menú editado", 16, dish_id)
    service.set_recipe(dish_id, {ingredient_id: 0.3})
    assert service.recipe(dish_id).iloc[0]["quantity"] == 0.3
    assert service.ingredients().iloc[0]["cost"] == 5
    service.set_ingredient_active(ingredient_id, False)
    assert service.ingredients().empty


def test_waste_cost_uses_lot_prices_and_cannot_overdraw(service):
    rice = ingredient(service)
    receipt(service, rice, 1, "p1", cost=4)
    receipt(service, rice, 1, "p2", cost=6)
    service.record_waste(rice, 1.5, "Deterioro", business_today(), "w1")
    assert service.waste().iloc[0]["cost"] == 7
    with pytest.raises(DomainError):
        service.record_waste(rice, 1, "Deterioro", business_today(), "w2")
    assert service.stock(business_today()).iloc[0]["available"] == 0.5


def test_future_and_backdated_movements_are_rejected(service):
    rice, dish = setup_dish(service)
    today = business_today()
    receipt(service, rice, 3)
    with pytest.raises(DomainError, match="futura"):
        receipt(service, rice, 1, "future", day=today + timedelta(days=1))
    with pytest.raises(DomainError, match="posterior"):
        service.record_sale({dish: 1}, today - timedelta(days=1), "past")
    assert service.sales().empty
    assert len(service.purchases()) == 1


def test_demo_is_explicit_atomic_and_idempotent(tmp_path):
    demo = RestaurantService(tmp_path / "demo.sqlite3")
    own = RestaurantService(tmp_path / "restaurant.sqlite3")
    seed_demo(demo)
    assert own.ingredients().empty
    assert len(demo.demand_history()) == 90 * 7
    assert set(demo.demand_history()["source"]) == {"synthetic_demo"}
    assert demo.sales().empty
    history = demo.demand_history()
    ingredient_id = int(demo.ingredients().iloc[0]["id"])
    demo.record_waste(ingredient_id, 0.5, "Prueba", business_today(), "w1")
    seed_demo(demo)
    assert len(demo.waste()) == 1
    pd.testing.assert_frame_equal(demo.demand_history(), history)
    with pytest.raises(DomainError):
        seed_demo(own)


def test_sql_like_names_are_plain_data_and_duplicates_actionable(service):
    ingredient(service, "Arroz'); DROP TABLE dishes; --")
    service.save_dish("Menú", 10)
    with pytest.raises(DomainError, match="existe"):
        service.save_dish("menú", 15)
    assert len(service.dishes()) == 1
