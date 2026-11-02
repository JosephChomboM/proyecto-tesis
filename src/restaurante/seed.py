"""Explicit synthetic demonstration setup; never called for an own restaurant."""

from datetime import timedelta

import numpy as np

from .db import transaction
from .service import DomainError, business_today


def seed_demo(service, today=None):
    """Seed once, atomically. Existing demo changes survive every restart."""
    today = today or business_today()
    if service.db_path.name == "restaurant.sqlite3":
        raise DomainError("Los datos de demostración no se cargan en el restaurante propio.")
    with transaction(service.db_path) as connection:
        if connection.execute("SELECT value FROM metadata WHERE key='demo_seeded'").fetchone():
            return
        if connection.execute("SELECT 1 FROM ingredients LIMIT 1").fetchone():
            raise DomainError("La demostración necesita una base vacía; no se reemplazaron tus datos.")
        ingredients = [
            ("Pollo", "kg", 10.5, 1.0, 3, 2.0, 18.0),
            ("Arroz", "kg", 4.2, 5.0, 90, 3.0, 30.0),
            ("Papa", "kg", 3.0, 5.0, 14, 3.0, 25.0),
            ("Cebolla", "kg", 3.2, 1.0, 14, 1.0, 8.0),
            ("Tomate", "kg", 4.5, 1.0, 5, 1.0, 5.0),
            ("Aceite", "L", 8.0, 1.0, 120, 1.0, 8.0),
            ("Carne de res", "kg", 28.0, 1.0, 3, 1.5, 8.0),
        ]
        for name, unit, cost, pack, life, safety, stock in ingredients:
            ingredient_id = connection.execute(
                "INSERT INTO ingredients(name,unit,cost,pack_size,shelf_life_days,safety_stock) "
                "VALUES (?,?,?,?,?,?)", (name, unit, cost, pack, life, safety)).lastrowid
            connection.execute(
                "INSERT INTO purchases(ingredient_id,quantity,remaining,unit_cost,received_on,expires_on)"
                " VALUES (?,?,?,?,?,?)", (ingredient_id, stock, stock, cost, today.isoformat(),
                                         (today + timedelta(days=life - 1)).isoformat()))
        dishes = [
            ("Arroz con pollo", 16.0, {1: 0.22, 2: 0.15, 4: 0.04, 6: 0.02}),
            ("Lomo saltado", 24.0, {7: 0.20, 2: 0.13, 3: 0.20, 4: 0.06, 5: 0.06, 6: 0.03}),
            ("Pollo a la plancha", 19.0, {1: 0.25, 3: 0.20, 5: 0.06, 6: 0.02}),
        ]
        for name, price, recipe in dishes:
            dish_id = connection.execute("INSERT INTO dishes(name,price) VALUES (?,?)",
                                         (name, price)).lastrowid
            connection.executemany("INSERT INTO recipes VALUES (?,?,?)",
                                   [(dish_id, ingredient, qty) for ingredient, qty in recipe.items()])
        rng = np.random.default_rng(42)
        for offset in range(90, 0, -1):
            day = today - timedelta(days=offset)
            factor = 1.20 if day.weekday() >= 5 else 1.0
            demand = {i: 0.0 for i in range(1, len(ingredients) + 1)}
            for (_, _, recipe), base in zip(dishes, (25, 15, 18), strict=True):
                portions = max(0, int(rng.normal(base * factor, base * 0.12)))
                for ingredient, qty in recipe.items():
                    demand[ingredient] += portions * qty
            connection.executemany("INSERT INTO demo_demand VALUES (?,?,?)",
                                   [(day.isoformat(), ingredient, qty) for ingredient, qty in demand.items()])
        connection.execute("INSERT INTO metadata VALUES ('demo_seeded',?)", (today.isoformat(),))
        connection.execute("INSERT INTO metadata VALUES ('data_source','synthetic_demo_unvalidated')")
