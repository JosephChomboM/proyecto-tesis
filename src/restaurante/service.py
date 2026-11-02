"""Durable restaurant workflows, independent from Streamlit."""

import hashlib
import json
import math
import sqlite3
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from .db import connect, initialize, transaction

EPSILON = 1e-8


class DomainError(ValueError):
    """A rejected operation with a user-facing explanation."""


def business_today():
    return datetime.now(ZoneInfo("America/Lima")).date()


def _date(value):
    try:
        if isinstance(value, datetime):
            return value.date().isoformat()
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError):
        raise DomainError("Ingresa una fecha válida.") from None


def _number(value, label, positive=False, integer=False):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise DomainError(f"{label}: ingresa un número válido.") from None
    if isinstance(value, bool) or not math.isfinite(result):
        raise DomainError(f"{label}: ingresa un número finito.")
    # This operational bound also prevents finite inputs overflowing calculated
    # amounts or SQLite integer bindings when multiplied by portions/recipes.
    if result > 1_000_000_000:
        raise DomainError(f"{label}: el máximo permitido es 1 000 000 000.")
    if result < 0 or (positive and result <= 0):
        raise DomainError(f"{label}: debe ser {'mayor que cero' if positive else 'cero o mayor'}.")
    if positive and result < 0.000001:
        raise DomainError(f"{label}: la cantidad mínima admitida es 0.000001.")
    if integer and not result.is_integer():
        raise DomainError(f"{label}: debe ser un número entero.")
    return int(result) if integer else result


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise DomainError(f"{label}: completa este campo.")
    if len(value.strip()) > 200:
        raise DomainError(f"{label}: usa como máximo 200 caracteres.")
    return value.strip()


class RestaurantService:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        initialize(self.db_path)

    def _frame(self, query, params=()):
        connection = connect(self.db_path)
        try:
            return pd.read_sql_query(query, connection, params=params)
        finally:
            connection.close()

    @staticmethod
    def _get(connection, table, item_id, active=False):
        # Table names are internal constants, never external inputs.
        row = connection.execute(f"SELECT * FROM {table} WHERE id=?", (int(item_id),)).fetchone()
        if row is None:
            raise DomainError("El registro seleccionado ya no existe.")
        if active and not row["active"]:
            raise DomainError(f"{row['name']} está desactivado.")
        return row

    def ingredients(self, include_inactive=False):
        return self._frame("SELECT * FROM ingredients" + ("" if include_inactive else " WHERE active=1")
                           + " ORDER BY name")

    def save_ingredient(self, name, unit, cost, pack_size, shelf_life_days, safety_stock,
                        ingredient_id=None):
        if ingredient_id is not None:
            ingredient_id = _number(ingredient_id, "Insumo", positive=True, integer=True)
        name, unit = _text(name, "Nombre"), _text(unit, "Unidad")
        cost = _number(cost, "Costo")
        pack_size = _number(pack_size, "Presentación", positive=True)
        shelf_life_days = _number(shelf_life_days, "Vida útil", positive=True, integer=True)
        safety_stock = _number(safety_stock, "Stock de seguridad")
        try:
            with transaction(self.db_path) as connection:
                if ingredient_id is None:
                    cursor = connection.execute(
                        "INSERT INTO ingredients(name,unit,cost,pack_size,shelf_life_days,safety_stock)"
                        " VALUES (?,?,?,?,?,?)",
                        (name, unit, cost, pack_size, shelf_life_days, safety_stock))
                    return cursor.lastrowid
                old = self._get(connection, "ingredients", ingredient_id)
                used = connection.execute(
                    "SELECT 1 FROM purchases WHERE ingredient_id=? UNION ALL "
                    "SELECT 1 FROM demo_demand WHERE ingredient_id=? LIMIT 1",
                    (ingredient_id, ingredient_id)).fetchone()
                if old["unit"] != unit and used:
                    raise DomainError("No se puede cambiar la unidad de un insumo con movimientos.")
                connection.execute(
                    "UPDATE ingredients SET name=?,unit=?,cost=?,pack_size=?,shelf_life_days=?,"
                    "safety_stock=? WHERE id=?",
                    (name, unit, cost, pack_size, shelf_life_days, safety_stock, ingredient_id))
                return int(ingredient_id)
        except sqlite3.IntegrityError:
            raise DomainError("Ya existe un insumo con ese nombre.") from None

    def set_ingredient_active(self, ingredient_id, active):
        self._set_active("ingredients", ingredient_id, active)

    def _set_active(self, table, item_id, active):
        item_id = _number(item_id, "Identificador", positive=True, integer=True)
        if not isinstance(active, (bool, int)) or active not in (True, False, 0, 1):
            raise DomainError("Estado inválido.")
        with transaction(self.db_path) as connection:
            self._get(connection, table, item_id)
            connection.execute(f"UPDATE {table} SET active=? WHERE id=?", (int(active), item_id))

    def dishes(self, include_inactive=False):
        return self._frame("SELECT * FROM dishes" + ("" if include_inactive else " WHERE active=1")
                           + " ORDER BY name")

    def save_dish(self, name, price, dish_id=None):
        if dish_id is not None:
            dish_id = _number(dish_id, "Plato", positive=True, integer=True)
        name, price = _text(name, "Nombre"), _number(price, "Precio")
        try:
            with transaction(self.db_path) as connection:
                if dish_id is None:
                    return connection.execute("INSERT INTO dishes(name,price) VALUES (?,?)",
                                              (name, price)).lastrowid
                self._get(connection, "dishes", dish_id)
                connection.execute("UPDATE dishes SET name=?,price=? WHERE id=?",
                                   (name, price, dish_id))
                return int(dish_id)
        except sqlite3.IntegrityError:
            raise DomainError("Ya existe un plato con ese nombre.") from None

    def set_dish_active(self, dish_id, active):
        self._set_active("dishes", dish_id, active)

    def recipe(self, dish_id):
        dish_id = _number(dish_id, "Plato", positive=True, integer=True)
        return self._frame("SELECT ingredient_id,quantity FROM recipes WHERE dish_id=? "
                           "ORDER BY ingredient_id", (dish_id,))

    @staticmethod
    def _items(items, integer=False):
        if not isinstance(items, dict) or not items:
            raise DomainError("Agrega al menos un elemento.")
        result = {}
        for item_id, quantity in items.items():
            item_id = _number(item_id, "Identificador", positive=True, integer=True)
            quantity = _number(quantity, "Cantidad", positive=True, integer=integer)
            result[item_id] = result.get(item_id, 0) + quantity
        return result

    def set_recipe(self, dish_id, items):
        dish_id = _number(dish_id, "Plato", positive=True, integer=True)
        items = self._items(items)
        with transaction(self.db_path) as connection:
            self._get(connection, "dishes", dish_id, active=True)
            for ingredient_id in items:
                self._get(connection, "ingredients", ingredient_id, active=True)
            connection.execute("DELETE FROM recipes WHERE dish_id=?", (dish_id,))
            connection.executemany("INSERT INTO recipes VALUES (?,?,?)",
                                   [(dish_id, key, value) for key, value in items.items()])

    @staticmethod
    def _request(connection, key, kind, payload):
        key = _text(key, "Identificador de operación")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        previous = connection.execute("SELECT * FROM requests WHERE request_key=?", (key,)).fetchone()
        if previous:
            if previous["kind"] != kind or previous["payload_hash"] != digest:
                raise DomainError("Esta operación ya fue registrada con otros datos. Inicia una nueva.")
            return key, digest, previous["result_id"]
        return key, digest, None

    @staticmethod
    def _finish(connection, key, kind, digest, result_id):
        connection.execute("INSERT INTO requests VALUES (?,?,?,?)", (key, kind, digest, result_id))
        return result_id

    @staticmethod
    def _chronological(connection, day):
        if day > business_today().isoformat():
            raise DomainError("No se pueden registrar movimientos con fecha futura.")
        latest = connection.execute(
            "SELECT MAX(day) FROM (SELECT MAX(received_on) day FROM purchases UNION ALL "
            "SELECT MAX(sold_on) FROM sales UNION ALL SELECT MAX(occurred_on) FROM waste)"
        ).fetchone()[0]
        if latest and day < latest:
            raise DomainError(f"Registra el movimiento desde {latest}; existe un movimiento posterior.")

    def receive_purchase(self, ingredient_id, quantity, unit_cost, received_on, expires_on, request_key):
        ingredient_id = _number(ingredient_id, "Insumo", positive=True, integer=True)
        quantity = _number(quantity, "Cantidad", positive=True)
        unit_cost = _number(unit_cost, "Costo unitario")
        received_on, expires_on = _date(received_on), _date(expires_on)
        if expires_on < received_on:
            raise DomainError("El vencimiento no puede ser anterior a la recepción.")
        payload = [ingredient_id, quantity, unit_cost, received_on, expires_on]
        with transaction(self.db_path) as connection:
            key, digest, previous = self._request(connection, request_key, "purchase", payload)
            if previous is not None:
                return previous
            self._chronological(connection, received_on)
            self._get(connection, "ingredients", ingredient_id, active=True)
            result = connection.execute(
                "INSERT INTO purchases(ingredient_id,quantity,remaining,unit_cost,received_on,expires_on)"
                " VALUES (?,?,?,?,?,?)",
                (ingredient_id, quantity, quantity, unit_cost, received_on, expires_on)).lastrowid
            return self._finish(connection, key, "purchase", digest, result)

    @staticmethod
    def _eligible(connection, ingredient_id, day, include_expired=False):
        return connection.execute(
            "SELECT * FROM purchases WHERE ingredient_id=? AND remaining>? AND received_on<=?"
            + ("" if include_expired else " AND expires_on>=?") + " ORDER BY received_on,id",
            (ingredient_id, EPSILON, day) if include_expired
            else (ingredient_id, EPSILON, day, day)).fetchall()

    @staticmethod
    def _allocate(connection, lots, quantity):
        allocation = []
        for lot in lots:
            amount = min(quantity, lot["remaining"])
            if amount > EPSILON:
                connection.execute("UPDATE purchases SET remaining=MAX(0,remaining-?) WHERE id=?",
                                   (amount, lot["id"]))
                allocation.append((lot, amount))
                quantity -= amount
            if quantity <= EPSILON:
                break
        return allocation

    def record_sale(self, items, sold_on, request_key):
        items, sold_on = self._items(items, integer=True), _date(sold_on)
        payload = [sorted(items.items()), sold_on]
        with transaction(self.db_path) as connection:
            key, digest, previous = self._request(connection, request_key, "sale", payload)
            if previous is not None:
                return previous
            self._chronological(connection, sold_on)
            requirements, lines, total = {}, [], 0.0
            for dish_id, portions in items.items():
                dish = self._get(connection, "dishes", dish_id, active=True)
                recipe = connection.execute("SELECT * FROM recipes WHERE dish_id=?", (dish_id,)).fetchall()
                if not recipe:
                    raise DomainError(f"Completa la receta de {dish['name']} antes de venderlo.")
                lines.append((dish, portions))
                total += dish["price"] * portions
                for row in recipe:
                    ingredient = self._get(connection, "ingredients", row["ingredient_id"], active=True)
                    ingredient_id = ingredient["id"]
                    requirements[ingredient_id] = (requirements.get(ingredient_id, 0)
                                                   + row["quantity"] * portions)
            lots_by_ingredient = {}
            for ingredient_id, required in requirements.items():
                lots = self._eligible(connection, ingredient_id, sold_on)
                available = sum(lot["remaining"] for lot in lots)
                if available + EPSILON < required:
                    ingredient = self._get(connection, "ingredients", ingredient_id)
                    raise DomainError(f"Stock insuficiente de {ingredient['name']}: "
                                      f"disponible {available:.3f} {ingredient['unit']}; "
                                      f"necesario {required:.3f}.")
                lots_by_ingredient[ingredient_id] = lots
            if not math.isfinite(total):
                raise DomainError("El total de la venta excede el límite permitido.")
            sale_id = connection.execute("INSERT INTO sales(sold_on,total) VALUES (?,?)",
                                         (sold_on, total)).lastrowid
            connection.executemany(
                "INSERT INTO sale_lines(sale_id,dish_id,dish_name,portions,unit_price) VALUES (?,?,?,?,?)",
                [(sale_id, dish["id"], dish["name"], portions, dish["price"]) for dish, portions in lines])
            for ingredient_id, required in requirements.items():
                for lot, amount in self._allocate(connection, lots_by_ingredient[ingredient_id], required):
                    connection.execute("INSERT INTO consumption(sale_id,ingredient_id,lot_id,quantity,"
                                       "unit_cost) VALUES (?,?,?,?,?)",
                                       (sale_id, ingredient_id, lot["id"], amount, lot["unit_cost"]))
            return self._finish(connection, key, "sale", digest, sale_id)

    def record_waste(self, ingredient_id, quantity, reason, occurred_on, request_key):
        ingredient_id = _number(ingredient_id, "Insumo", positive=True, integer=True)
        quantity = _number(quantity, "Cantidad", positive=True)
        reason, occurred_on = _text(reason, "Motivo"), _date(occurred_on)
        with transaction(self.db_path) as connection:
            key, digest, previous = self._request(connection, request_key, "waste",
                                                  [ingredient_id, quantity, reason, occurred_on])
            if previous is not None:
                return previous
            self._chronological(connection, occurred_on)
            self._get(connection, "ingredients", ingredient_id)
            lots = self._eligible(connection, ingredient_id, occurred_on, include_expired=True)
            if sum(lot["remaining"] for lot in lots) + EPSILON < quantity:
                raise DomainError("La merma supera la cantidad física del insumo.")
            allocation = self._allocate(connection, lots, quantity)
            cost = sum(lot["unit_cost"] * amount for lot, amount in allocation)
            result = connection.execute(
                "INSERT INTO waste(ingredient_id,quantity,cost,reason,occurred_on) VALUES (?,?,?,?,?)",
                (ingredient_id, quantity, cost, reason, occurred_on)).lastrowid
            connection.executemany("INSERT INTO waste_allocations VALUES (?,?,?)",
                                   [(result, lot["id"], amount) for lot, amount in allocation])
            return self._finish(connection, key, "waste", digest, result)

    def expire_stock(self, as_of):
        as_of = _date(as_of)
        with transaction(self.db_path) as connection:
            self._chronological(connection, as_of)
            expired = connection.execute("SELECT * FROM purchases WHERE remaining>? AND expires_on<?",
                                         (EPSILON, as_of)).fetchall()
            for lot in expired:
                result = connection.execute(
                    "INSERT INTO waste(ingredient_id,quantity,cost,reason,occurred_on) VALUES (?,?,?,?,?)",
                    (lot["ingredient_id"], lot["remaining"], lot["remaining"] * lot["unit_cost"],
                     "Vencimiento", as_of)).lastrowid
                connection.execute("INSERT INTO waste_allocations VALUES (?,?,?)",
                                   (result, lot["id"], lot["remaining"]))
                connection.execute("UPDATE purchases SET remaining=0 WHERE id=?", (lot["id"],))
            return len(expired)

    def stock(self, as_of):
        day = _date(as_of)
        return self._frame(
            "SELECT i.id ingredient_id,i.name,i.unit,"
            "COALESCE(SUM(CASE WHEN p.expires_on>=? AND p.received_on<=? THEN p.remaining ELSE 0 END),0)"
            " available,COALESCE(SUM(CASE WHEN p.expires_on<? AND p.received_on<=? "
            "THEN p.remaining ELSE 0 END),0) expired,i.cost,i.pack_size,i.safety_stock "
            "FROM ingredients i LEFT JOIN purchases p ON p.ingredient_id=i.id "
            "GROUP BY i.id ORDER BY i.name", (day, day, day, day))

    def lots(self):
        return self._frame("SELECT p.*,i.name,i.unit FROM purchases p JOIN ingredients i "
                           "ON i.id=p.ingredient_id ORDER BY received_on,p.id")

    def sales(self):
        return self._frame("SELECT s.id,s.sold_on,s.total,SUM(l.portions) portions FROM sales s "
                           "JOIN sale_lines l ON l.sale_id=s.id GROUP BY s.id ORDER BY s.id DESC")

    def purchases(self):
        return self._frame("SELECT p.*,i.name,i.unit,p.quantity*p.unit_cost total FROM purchases p "
                           "JOIN ingredients i ON i.id=p.ingredient_id ORDER BY p.id DESC")

    def waste(self):
        return self._frame("SELECT w.*,i.name,i.unit FROM waste w JOIN ingredients i "
                           "ON i.id=w.ingredient_id ORDER BY w.id DESC")

    def demand_history(self):
        return self._frame(
            "SELECT s.sold_on date,c.ingredient_id,SUM(c.quantity) quantity,'operational' source "
            "FROM consumption c JOIN sales s ON s.id=c.sale_id GROUP BY s.sold_on,c.ingredient_id "
            "UNION ALL SELECT date,ingredient_id,quantity,'synthetic_demo' source FROM demo_demand "
            "ORDER BY date,ingredient_id")
