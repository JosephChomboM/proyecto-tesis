"""SQLite storage. Each service call owns and closes its connection."""

import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4

_active = ContextVar("restaurant_transaction", default=None)

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
CREATE TABLE IF NOT EXISTS day_closures (
 day TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('complete','closed')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS daily_demand (
 day TEXT NOT NULL REFERENCES day_closures(day),
 ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
 quantity REAL NOT NULL CHECK(quantity>=0),
 PRIMARY KEY(day,ingredient_id)
);
CREATE TABLE IF NOT EXISTS unmet_demand (
 id INTEGER PRIMARY KEY, dish_id INTEGER NOT NULL REFERENCES dishes(id),
 portions INTEGER NOT NULL CHECK(portions>0), day TEXT NOT NULL, reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS unmet_ingredients (
 event_id INTEGER NOT NULL REFERENCES unmet_demand(id),
 ingredient_id INTEGER NOT NULL REFERENCES ingredients(id), quantity REAL NOT NULL,
 PRIMARY KEY(event_id,ingredient_id)
);
CREATE TABLE IF NOT EXISTS stock_adjustments (
 id INTEGER PRIMARY KEY, ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
 expected REAL NOT NULL, counted REAL NOT NULL, reason TEXT NOT NULL, day TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS adjustment_lots (
 purchase_id INTEGER PRIMARY KEY REFERENCES purchases(id),
 adjustment_id INTEGER NOT NULL REFERENCES stock_adjustments(id)
);
UPDATE metadata SET value='2' WHERE key='schema_version';
CREATE TABLE IF NOT EXISTS calendar_events (
 id INTEGER PRIMARY KEY, day TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('promotion','reservation','closure','holiday','other','cancelled')),
 name TEXT NOT NULL, recorded_on TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS events_day ON calendar_events(day,id);
UPDATE metadata SET value='3' WHERE key='schema_version';
CREATE TABLE IF NOT EXISTS import_batches (
 digest TEXT PRIMARY KEY, kind TEXT NOT NULL, filename TEXT NOT NULL,
 row_count INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS import_references (
 kind TEXT NOT NULL, reference TEXT NOT NULL, payload_hash TEXT NOT NULL,
 batch_digest TEXT NOT NULL REFERENCES import_batches(digest), PRIMARY KEY(kind,reference)
);
CREATE TABLE IF NOT EXISTS opening_lots (
 purchase_id INTEGER PRIMARY KEY REFERENCES purchases(id),
 batch_digest TEXT NOT NULL REFERENCES import_batches(digest)
);
CREATE TABLE IF NOT EXISTS imported_history_days (
 day TEXT PRIMARY KEY, batch_digest TEXT NOT NULL REFERENCES import_batches(digest)
);
CREATE TABLE IF NOT EXISTS imported_sales (
 day TEXT NOT NULL REFERENCES imported_history_days(day), dish_id INTEGER NOT NULL REFERENCES dishes(id),
 portions INTEGER NOT NULL CHECK(portions>=0), unmet INTEGER NOT NULL CHECK(unmet>=0),
 PRIMARY KEY(day,dish_id)
);
CREATE TABLE IF NOT EXISTS imported_demand (
 day TEXT NOT NULL REFERENCES imported_history_days(day), ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
 quantity REAL NOT NULL CHECK(quantity>=0), PRIMARY KEY(day,ingredient_id)
);
UPDATE metadata SET value='4' WHERE key='schema_version';
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
    existing = active_connection(path)
    if existing is not None:
        savepoint = "nested_"+uuid4().hex
        existing.execute(f"SAVEPOINT {savepoint}")
        try:
            yield existing
        except BaseException:
            existing.execute(f"ROLLBACK TO {savepoint}")
            raise
        finally:
            existing.execute(f"RELEASE {savepoint}")
        return
    connection = connect(path)
    token = _active.set((Path(path).resolve(), connection))
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        _active.reset(token)
        connection.close()


def active_connection(path):
    active = _active.get()
    return active[1] if active and active[0] == Path(path).resolve() else None
