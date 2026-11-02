"""SQLite storage. Each service call owns and closes its connection."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT OR IGNORE INTO metadata VALUES ('schema_version', '1');
CREATE TABLE IF NOT EXISTS ingredients (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
 unit TEXT NOT NULL, cost REAL NOT NULL CHECK(cost >= 0),
 pack_size REAL NOT NULL CHECK(pack_size > 0),
 shelf_life_days INTEGER NOT NULL CHECK(shelf_life_days > 0),
 safety_stock REAL NOT NULL CHECK(safety_stock >= 0),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);
CREATE TABLE IF NOT EXISTS dishes (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
 price REAL NOT NULL CHECK(price >= 0), active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS recipes (
 dish_id INTEGER NOT NULL REFERENCES dishes(id),
 ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
 quantity REAL NOT NULL CHECK(quantity > 0), PRIMARY KEY(dish_id, ingredient_id)
);
CREATE TABLE IF NOT EXISTS purchases (
 id INTEGER PRIMARY KEY, ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
 quantity REAL NOT NULL CHECK(quantity > 0), remaining REAL NOT NULL CHECK(remaining >= 0),
 unit_cost REAL NOT NULL CHECK(unit_cost >= 0), received_on TEXT NOT NULL,
 expires_on TEXT NOT NULL CHECK(expires_on >= received_on)
);
CREATE TABLE IF NOT EXISTS sales (
 id INTEGER PRIMARY KEY, sold_on TEXT NOT NULL, total REAL NOT NULL CHECK(total >= 0)
);
CREATE TABLE IF NOT EXISTS sale_lines (
 id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id),
 dish_id INTEGER NOT NULL REFERENCES dishes(id), dish_name TEXT NOT NULL,
 portions INTEGER NOT NULL CHECK(portions > 0), unit_price REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS consumption (
 id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id),
 ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
 lot_id INTEGER NOT NULL REFERENCES purchases(id), quantity REAL NOT NULL CHECK(quantity > 0),
 unit_cost REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS waste (
 id INTEGER PRIMARY KEY, ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
 quantity REAL NOT NULL CHECK(quantity > 0), cost REAL NOT NULL CHECK(cost >= 0),
 reason TEXT NOT NULL, occurred_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS waste_allocations (
 waste_id INTEGER NOT NULL REFERENCES waste(id), lot_id INTEGER NOT NULL REFERENCES purchases(id),
 quantity REAL NOT NULL CHECK(quantity > 0)
);
CREATE TABLE IF NOT EXISTS requests (
 request_key TEXT PRIMARY KEY, kind TEXT NOT NULL, payload_hash TEXT NOT NULL,
 result_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS demo_demand (
 date TEXT NOT NULL, ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
 quantity REAL NOT NULL CHECK(quantity >= 0), PRIMARY KEY(date, ingredient_id)
);
CREATE INDEX IF NOT EXISTS lots_available ON purchases(ingredient_id, received_on, id);
CREATE INDEX IF NOT EXISTS sales_date ON sales(sold_on);
"""


def connect(path):
    connection = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=10000")
    return connection


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = connect(path)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(SCHEMA)
    finally:
        connection.close()


@contextmanager
def transaction(path):
    connection = connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
