"""Bounded CSV ingestion, atomic writes and dry-run previews using domain operations."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import tempfile
import unicodedata
from pathlib import Path

import pandas as pd

from .db import transaction
from .service import DomainError, RestaurantService, _number, _text, business_today

SCHEMAS = {
    "insumos": ["insumo", "unidad", "costo_unitario", "presentacion", "vida_util_dias", "stock_seguridad"],
    "platos": ["plato", "precio"],
    "recetas": ["plato", "insumo", "cantidad", "unidad"],
    "stock_inicial": ["insumo", "cantidad", "unidad", "costo_unitario", "fecha", "vencimiento"],
    "compras": ["referencia", "insumo", "cantidad", "unidad", "costo_unitario", "fecha", "vencimiento"],
    "ventas_historicas": ["fecha", "plato", "porciones"],
}
TITLES = {"insumos": "Insumos", "platos": "Platos", "recetas": "Recetas",
          "stock_inicial": "Stock inicial", "compras": "Compras recibidas",
          "ventas_historicas": "Ventas históricas"}
ALIASES = {
    "insumo": ["nombre", "ingrediente", "ingredient", "producto", "name"],
    "plato": ["nombre", "dish", "dish_name", "descripcion"],
    "unidad": ["unit", "unidad_medida"], "cantidad": ["quantity", "stock", "existencias"],
    "porciones": ["cantidad", "portions", "vendidos", "unidades_vendidas"],
    "costo_unitario": ["unit_cost", "cost", "costo", "costo_referencia"],
    "precio": ["price", "precio_venta"], "presentacion": ["pack_size", "empaque"],
    "vida_util_dias": ["shelf_life_days", "vida_util"], "stock_seguridad": ["safety_stock", "reserva"],
    "fecha": ["date", "sold_on", "received_on", "fecha_venta", "fecha_recepcion"],
    "vencimiento": ["expires_on", "fecha_vencimiento"],
    "referencia": ["reference", "documento", "codigo", "id_externo"],
    "no_atendidas": ["unmet", "pedidos_rechazados"],
}
UNITS = {"kg": "kg", "kilo": "kg", "kilos": "kg", "kilogramo": "kg", "kilogramos": "kg",
         "g": "g", "gramo": "g", "gramos": "g", "l": "L", "litro": "L", "litros": "L",
         "ml": "ml", "mililitro": "ml", "mililitros": "ml", "unidad": "unidad", "unidades": "unidad", "und": "unidad"}


def normalized(value):
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower().strip()
    return "_".join(text.replace("-", " ").replace("_", " ").split())


def read_csv(content, separator="auto"):
    if not isinstance(content, bytes) or not content or len(content) > 5_000_000:
        raise DomainError("Selecciona un CSV de hasta 5 MB.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252")
    if "\x00" in text:
        raise DomainError("El archivo no parece un CSV de texto.")
    try:
        delimiter = csv.Sniffer().sniff(text[:10000], delimiters=",;\t").delimiter if separator == "auto" else separator
        header = next(csv.reader(io.StringIO(text), delimiter=delimiter))
        if len(set(map(normalized, header))) != len(header) or any(not str(x).strip() for x in header):
            raise DomainError("Hay encabezados vacíos o repetidos. Corrígelos en el archivo.")
        frame = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False)
    except (csv.Error, StopIteration, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise DomainError("No se pudo leer el CSV. Revisa el separador y las columnas.") from exc
    if frame.empty or len(frame) > 10000:
        raise DomainError("El CSV debe tener entre 1 y 10000 filas.")
    return frame


def suggest_mapping(frame, kind):
    required = SCHEMAS[kind]+(["no_atendidas"] if kind == "ventas_historicas" else [])
    columns = {normalized(name): name for name in frame.columns}
    return {field: next((columns[name] for name in [field, *ALIASES.get(field, [])] if name in columns), None)
            for field in required}


def _numeric(value, field, decimal):
    text = str(value).strip()
    other = "," if decimal == "." else "."
    if other in text:
        raise DomainError(f"{field}: usa el decimal elegido y no uses separadores de miles.")
    return _number(text.replace(",", "."), field,
                   positive=field in {"cantidad", "presentacion", "vida_util_dias"},
                   integer=field in {"porciones", "vida_util_dias", "no_atendidas"})


def prepare(frame, kind, mapping=None, decimal=".", date_format="DD/MM/AAAA"):
    if kind not in SCHEMAS or decimal not in {".", ","} or date_format not in {"DD/MM/AAAA", "AAAA-MM-DD"}:
        raise DomainError("Tipo de importación, decimal o formato de fecha inválido.")
    if frame.empty or len(frame) > 10000:
        raise DomainError("Ingresa entre 1 y 10000 filas.")
    mapping = suggest_mapping(frame, kind) if mapping is None else mapping
    missing = [field for field in SCHEMAS[kind] if mapping.get(field) not in frame]
    if missing:
        raise DomainError("Asocia estas columnas: "+", ".join(missing))
    selected = [value for value in mapping.values() if value is not None]
    if len(selected) != len(set(selected)):
        raise DomainError("No asocies la misma columna a dos campos distintos.")
    rows = []
    numeric = {"costo_unitario", "presentacion", "vida_util_dias", "stock_seguridad", "precio", "cantidad", "porciones", "no_atendidas"}
    for position, (_, source) in enumerate(frame.iterrows(), start=2):
        try:
            row = {}
            for field in SCHEMAS[kind]+(["no_atendidas"] if kind == "ventas_historicas" else []):
                column = mapping.get(field)
                value = source[column] if column is not None else 0
                if field in numeric:
                    row[field] = _numeric(value, field, decimal)
                elif field in {"fecha", "vencimiento"}:
                    fmt = "%d/%m/%Y" if date_format == "DD/MM/AAAA" else "%Y-%m-%d"
                    row[field] = pd.to_datetime(str(value).strip(), format=fmt, errors="raise").date().isoformat()
                elif field == "unidad":
                    row[field] = UNITS.get(normalized(value))
                    if row[field] is None:
                        raise DomainError("Unidad desconocida. Usa kg, g, L, ml o unidad.")
                else:
                    row[field] = _text(str(value), field)
            row["_line"] = position
            rows.append(row)
        except (ValueError, TypeError, OverflowError) as exc:
            raise DomainError(f"Fila {position}: {exc}") from exc
    clean = pd.DataFrame(rows)
    unique = {"insumos": ["insumo"], "platos": ["plato"], "recetas": ["plato", "insumo"],
              "ventas_historicas": ["fecha", "plato"], "compras": ["referencia"]}.get(kind)
    comparison = clean.drop(columns="_line").map(lambda value: value.casefold().strip() if isinstance(value, str) else value)
    duplicates = comparison.duplicated(unique, keep=False)
    if duplicates.any():
        raise DomainError("Filas repetidas o claves duplicadas: "+", ".join(map(str, clean.loc[duplicates, "_line"])))
    return clean


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                                    separators=(",", ":")).encode()).hexdigest()


def _catalog(service, kind):
    frame = service.ingredients(include_inactive=True) if kind == "insumos" else service.dishes(include_inactive=True)
    if frame.name.str.strip().str.casefold().duplicated().any():
        raise DomainError("Hay nombres ambiguos en el catálogo. Diferéncialos antes de importar.")
    return {row["name"].strip().casefold(): row for row in frame.to_dict("records")}


def _resolve(catalog, name):
    item = catalog.get(name.strip().casefold())
    if item is None:
        raise DomainError(f"No existe «{name}». Créalo primero en la configuración.")
    if not item["active"]:
        raise DomainError(f"«{name}» está inactivo. Revísalo en Catálogo.")
    return item


def apply_import(service, kind, prepared, *, filename="Ingreso desde pantalla", complete_days=False):
    """Single transaction includes audit and all nested service calls. No silent overwrites."""
    if kind not in SCHEMAS or not set(SCHEMAS[kind]+["_line"]) <= set(prepared):
        raise DomainError("Valida la tabla antes de guardarla.")
    # Revalidate canonical values, even when a caller bypasses the CSV UI.
    raw = prepared.drop(columns="_line").astype(str)
    prepared = prepare(raw, kind, {column: column for column in raw}, date_format="AAAA-MM-DD")
    records = prepared.drop(columns="_line").to_dict("records")
    fingerprint = _digest({"kind": kind, "rows": sorted(records, key=lambda row: json.dumps(row, sort_keys=True))})
    with transaction(service.db_path) as connection:
        previous = connection.execute("SELECT row_count FROM import_batches WHERE digest=?", (fingerprint,)).fetchone()
        if previous:
            return {"digest": fingerprint, "created": 0, "unchanged": int(previous[0]), "already_imported": True}
        connection.execute("INSERT INTO import_batches(digest,kind,filename,row_count) VALUES (?,?,?,?)",
                           (fingerprint, kind, Path(filename).name[:200], len(records)))
        ingredients, dishes = _catalog(service, "insumos"), _catalog(service, "platos")
        created, unchanged = 0, 0
        if kind == "stock_inicial":
            if prepared.fecha.nunique() != 1:
                raise DomainError("El stock inicial necesita una única fecha de conteo para todos sus lotes.")
            occupied = connection.execute("SELECT (SELECT COUNT(*) FROM purchases)+(SELECT COUNT(*) FROM sales)"
                "+(SELECT COUNT(*) FROM waste)+(SELECT COUNT(*) FROM stock_adjustments)+(SELECT COUNT(*) FROM unmet_demand)").fetchone()[0]
            if occupied:
                raise DomainError("El stock inicial se registra una sola vez, antes de los movimientos. Para corregir existencias usa Stock y mermas.")
        if kind == "ventas_historicas":
            if not complete_days:
                raise DomainError("Confirma que cada jornada incluida contiene todos sus platos y revisaste las recetas.")
            days = sorted(prepared.fecha.unique())
            first_operation = connection.execute("SELECT MIN(day) FROM (SELECT received_on day FROM purchases UNION ALL "
                "SELECT sold_on FROM sales UNION ALL SELECT occurred_on FROM waste UNION ALL "
                "SELECT day FROM unmet_demand UNION ALL SELECT day FROM stock_adjustments UNION ALL SELECT day FROM day_closures)").fetchone()[0]
            for day in days:
                if day >= business_today().isoformat():
                    raise DomainError("El historial solo admite jornadas anteriores a hoy.")
                if first_operation and day >= first_operation:
                    raise DomainError("El historial debe ser anterior al primer movimiento operativo o stock inicial. No se mezclan jornadas ya registradas.")
                if connection.execute("SELECT 1 FROM imported_history_days WHERE day=?", (day,)).fetchone():
                    raise DomainError(f"La jornada {day} ya fue importada. No agregues un segundo resumen del mismo día.")
                connection.execute("INSERT INTO imported_history_days VALUES (?,?)", (day, fingerprint))
                connection.executemany("INSERT INTO imported_demand VALUES (?,?,0)",
                    [(day, item["id"]) for item in ingredients.values() if item["active"]])
        ordered = prepared.sort_values("fecha", kind="stable") if "fecha" in prepared else prepared
        recipe_groups = {}
        for row in ordered.to_dict("records"):
            try:
                if kind in {"insumos", "platos"}:
                    is_ingredient = kind == "insumos"
                    name = row["insumo" if is_ingredient else "plato"]
                    existing = (ingredients if is_ingredient else dishes).get(name.casefold())
                    fields = ({"unit": row["unidad"], "cost": row["costo_unitario"], "pack_size": row["presentacion"],
                               "shelf_life_days": row["vida_util_dias"], "safety_stock": row["stock_seguridad"]}
                              if is_ingredient else {"price": row["precio"]})
                    if existing:
                        equal = all(math.isclose(existing[key], value, rel_tol=1e-9, abs_tol=1e-9)
                                    if isinstance(value, (int, float)) else existing[key] == value for key, value in fields.items())
                        if not equal or not existing["active"]:
                            raise DomainError(f"«{name}» ya existe con otros datos o está inactivo. Edítalo en Catálogo; no se sobrescribe al importar.")
                        unchanged += 1
                        continue
                    if is_ingredient:
                        service.save_ingredient(name, row["unidad"], row["costo_unitario"], row["presentacion"], row["vida_util_dias"], row["stock_seguridad"])
                    else:
                        service.save_dish(name, row["precio"])
                    created += 1
                elif kind == "recetas":
                    dish, ingredient = _resolve(dishes, row["plato"]), _resolve(ingredients, row["insumo"])
                    if ingredient["unit"] != row["unidad"]:
                        raise DomainError(f"La unidad de {row['insumo']} es {ingredient['unit']}; no se convierte automáticamente.")
                    recipe_groups.setdefault(dish["id"], {})[ingredient["id"]] = row["cantidad"]
                elif kind in {"stock_inicial", "compras"}:
                    ingredient = _resolve(ingredients, row["insumo"])
                    if ingredient["unit"] != row["unidad"]:
                        raise DomainError(f"La unidad de {row['insumo']} debe ser {ingredient['unit']}.")
                    row_hash = _digest({key: (value.casefold() if key in {"insumo", "referencia"} else value)
                                        for key, value in row.items() if key != "_line"})
                    if kind == "compras":
                        prior = connection.execute("SELECT payload_hash FROM import_references WHERE kind=? AND reference=?",
                                                   (kind, row["referencia"].casefold())).fetchone()
                        if prior:
                            if prior[0] != row_hash:
                                raise DomainError("La referencia de compra ya fue usada con otros datos.")
                            unchanged += 1
                            continue
                    purchase = service.receive_purchase(ingredient["id"], row["cantidad"], row["costo_unitario"], row["fecha"], row["vencimiento"],
                                                        "csv-"+_digest([fingerprint, row_hash]))
                    if kind == "stock_inicial":
                        connection.execute("INSERT INTO opening_lots VALUES (?,?)", (purchase, fingerprint))
                    else:
                        connection.execute("INSERT INTO import_references VALUES (?,?,?,?)", (kind, row["referencia"].casefold(), row_hash, fingerprint))
                    created += 1
                else:
                    dish = _resolve(dishes, row["plato"])
                    recipe = service.recipe(dish["id"])
                    if recipe.empty:
                        raise DomainError(f"Completa la receta de {row['plato']} antes de importar sus ventas.")
                    connection.execute("INSERT INTO imported_sales VALUES (?,?,?,?)",
                                       (row["fecha"], dish["id"], row["porciones"], row["no_atendidas"]))
                    for item in recipe.itertuples():
                        ingredient = next(value for value in ingredients.values() if value["id"] == item.ingredient_id)
                        if not ingredient["active"]:
                            raise DomainError("La receta contiene un insumo inactivo.")
                        quantity = _number((row["porciones"]+row["no_atendidas"])*item.quantity, "Consumo estimado")
                        connection.execute("UPDATE imported_demand SET quantity=quantity+? WHERE day=? AND ingredient_id=?",
                                           (quantity, row["fecha"], item.ingredient_id))
                    created += 1
            except (ValueError, OverflowError) as exc:
                raise DomainError(f"Fila {row['_line']}: {exc}") from exc
        for dish_id, components in recipe_groups.items():
            old = service.recipe(dish_id)
            old_components = dict(zip(old.ingredient_id, old.quantity))
            if old_components:
                if old_components != components:
                    raise DomainError("Una receta ya existe con cantidades o componentes diferentes. Edítala en Catálogo; no se reemplaza al importar.")
                unchanged += len(components)
            else:
                service.set_recipe(dish_id, components)
                created += len(components)
        return {"digest": fingerprint, "created": created, "unchanged": unchanged, "already_imported": False}


def preview_import(service, kind, prepared, **kwargs):
    """Run the exact writer against a consistent disposable database snapshot."""
    with tempfile.TemporaryDirectory(prefix="mise-preview-") as folder:
        path = Path(folder)/"preview.sqlite3"
        path.write_bytes(service.backup())
        clone = RestaurantService(path)
        return apply_import(clone, kind, prepared, **kwargs)


def templates(today=None):
    today = today or business_today()
    day = today.isoformat()
    expiry = (today+pd.Timedelta(days=1)).isoformat()
    historical = (today-pd.Timedelta(days=7)).isoformat()
    examples = {
        "insumos": [["Pollo", "kg", 11, 1, 2, 1]], "platos": [["Arroz con pollo", 15]],
        "recetas": [["Arroz con pollo", "Pollo", .25, "kg"]],
        "stock_inicial": [["Pollo", 10, "kg", 11, day, expiry]],
        "compras": [["COMPRA-001-LINEA-1", "Pollo", 5, "kg", 11, day, expiry]],
        "ventas_historicas": [[historical, "Arroz con pollo", 30]],
    }
    return {kind: pd.DataFrame(rows, columns=SCHEMAS[kind]) for kind, rows in examples.items()}
