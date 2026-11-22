"""Administrator onboarding and CSV imports; no code or database IDs required."""

import hashlib

import streamlit as st

from .imports import (
    SCHEMAS,
    TITLES,
    apply_import,
    prepare,
    preview_import,
    read_csv,
    suggest_mapping,
    templates,
)
from .presentation import page_header

LABELS = {"insumo": "Insumo", "plato": "Plato", "unidad": "Unidad", "cantidad": "Cantidad",
          "costo_unitario": "Costo por unidad (S/)", "presentacion": "Cantidad por presentación",
          "vida_util_dias": "Vida útil (días)", "stock_seguridad": "Reserva mínima",
          "precio": "Precio por porción (S/)", "fecha": "Fecha", "vencimiento": "Vencimiento",
          "porciones": "Porciones vendidas", "no_atendidas": "Porciones no atendidas (opcional)",
          "referencia": "Referencia única de la línea de compra"}
LABELS.update({"name": "Nombre", "unit": "Unidad", "cost": "Costo de referencia (S/)",
               "pack_size": "Presentación", "shelf_life_days": "Vida útil (días)",
               "safety_stock": "Reserva", "active": "Activo", "price": "Precio (S/)",
               "filename": "Archivo o formulario", "row_count": "Filas", "kind": "Tipo de carga",
               "created_at": "Guardado el (UTC)", "origin": "Origen", "remaining": "Saldo",
               "received_on": "Fecha de entrada", "expires_on": "Vencimiento", "dish": "Plato",
               "portions": "Porciones vendidas", "unmet": "No atendidas", "date": "Fecha"})


def _show(frame):
    st.dataframe(frame.drop(columns=["_line", "digest"], errors="ignore").rename(columns=LABELS), hide_index=True,
                 width="stretch", height=min(420, 36*len(frame)+40))


def _history_confirmation(kind, key):
    if kind != "ventas_historicas":
        return False
    st.info("Este historial alimenta el pronóstico: no descuenta stock ni crea ingresos operativos. "
            "Se usarán las recetas actuales para estimar insumos. Incluye todos los platos de cada "
            "jornada; un día que no aparece seguirá siendo desconocido.")
    return st.checkbox("Confirmo que las jornadas incluidas están completas y revisé las recetas", key=key)


def _preview_and_save(service, kind, prepared, filename, complete_days, prefix):
    signature = hashlib.sha256((str(service.db_path)+kind+str(complete_days)+prepared.to_csv(index=False)).encode()).hexdigest()
    key = prefix+"_validated"
    if st.button("Validar y previsualizar" if prefix == "csv" else "Revisar tabla inicial", key=prefix+"_preview"):
        try:
            result = preview_import(service, kind, prepared, filename=filename, complete_days=complete_days)
            st.session_state[key] = {"signature": signature, "result": result}
        except ValueError as exc:
            st.session_state.pop(key, None)
            st.error(str(exc))
    validated = st.session_state.get(key)
    if validated and validated["signature"] == signature:
        result = validated["result"]
        st.success(f"Tabla válida. Filas nuevas: {result['created']}; sin cambios: {result['unchanged']}. "
                   "Todavía no se guardó nada.")
        _show(prepared.head(100))
        if len(prepared) > 100:
            st.caption(f"Vista previa de 100 de {len(prepared)} filas. Se validó el archivo completo.")
        if st.button("Confirmar importación" if prefix == "csv" else "Guardar tabla inicial",
                     key=prefix+"_save", type="primary"):
            try:
                result = apply_import(service, kind, prepared, filename=filename, complete_days=complete_days)
                st.session_state.pop(key, None)
                st.session_state["flash"] = f"Datos guardados en SQLite. Filas nuevas: {result['created']}; sin cambios: {result['unchanged']}."
                st.rerun()
            except ValueError as exc:
                st.session_state.pop(key, None)
                st.error(f"No se guardó el archivo: {exc}")


def setup_page(service, today):
    page_header("EMPIEZA AQUÍ", "Configuración inicial e importación",
                "Prepara tu restaurante desde esta pantalla o aprovecha los CSV que ya tienes.")
    ingredients, dishes, lots = service.ingredients(), service.dishes(), service.lots()
    recipes = service._frame("SELECT COUNT(DISTINCT dish_id) count FROM recipes").iloc[0]["count"]
    a, b, c, d = st.columns(4)
    a.metric("Insumos configurados", len(ingredients))
    b.metric("Platos configurados", len(dishes))
    c.metric("Platos con receta", int(recipes))
    d.metric("Lotes de inventario", len(lots))
    st.write("**Orden recomendado:** insumos → platos → recetas → stock inicial. "
             "Si tienes ventas antiguas, puedes incorporarlas después para pronosticar.")
    st.caption("Cada paso se guarda en la base de datos de este espacio. No necesitas completar "
               "todos los archivos ni modificar código. Para editar datos existentes usa Catálogo; "
               "para corregir existencias usa Stock y mermas.")
    manual, csv_tab, saved = st.tabs(["Completar en pantalla", "Importar CSV", "Revisar lo guardado"])
    samples = templates(today)
    with manual:
        kind = st.selectbox("Paso de configuración", [key for key in SCHEMAS if key != "compras"],
                            format_func=TITLES.get, key="setup_manual_kind")
        st.caption("Completa la fila o añade más filas como en una hoja de cálculo. "
                   "Las cantidades de recetas son por una porción, en la unidad del insumo.")
        row = samples[kind].copy()
        for column in ("insumo", "plato"):
            if column in row:
                row[column] = ""
        for column in ("cantidad", "porciones", "precio", "costo_unitario", "stock_seguridad"):
            if column in row:
                row[column] = 0.
        if kind == "stock_inicial":
            st.caption("Fecha = fecha del conteo inicial, no la fecha de una compra antigua. "
                       "Se registra una sola vez, antes de operar; no cuenta como gasto de compra.")
        complete_days = _history_confirmation(kind, "manual_complete_days")
        entered = st.data_editor(row, num_rows="dynamic", hide_index=True, width="stretch",
            key=f"setup_grid_{kind}", column_config={column: LABELS[column] for column in row})
        st.caption("Fechas en AAAA-MM-DD; decimales con punto. Ejemplo: 250 g de una receta "
                   "con almacén en kg se registran como 0.250 kg.")
        try:
            prepared = prepare(entered.astype(str), kind, date_format="AAAA-MM-DD")
            _preview_and_save(service, kind, prepared, "Configuración desde pantalla", complete_days, "manual")
        except (ValueError, TypeError) as exc:
            st.caption(f"Completa o corrige la tabla para continuar: {exc}")
    with csv_tab:
        kind = st.selectbox("Qué contiene tu archivo", list(SCHEMAS), format_func=TITLES.get, key="setup_csv_kind")
        st.download_button("Descargar CSV de ejemplo para este paso", samples[kind].to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"ejemplo_{kind}.csv", mime="text/csv")
        st.caption("La plantilla contiene una fila ilustrativa: reemplázala con tus datos. "
                   "Puedes usar tus encabezados y asociarlos abajo. Solo se guardan las columnas asociadas. "
                   "Se admite UTF-8 o CSV de Excel Windows.")
        if kind == "compras":
            st.caption("Cada línea necesita una referencia única, por ejemplo BOLETA-123-LINEA-1. "
                       "Sirve para evitar repetir compras al importar archivos que se superponen.")
        a, b, c = st.columns(3)
        separator = a.selectbox("Separador de columnas", ["Automático", "Coma", "Punto y coma", "Tabulación"])
        decimal_label = b.selectbox("Separador decimal", ["Punto: 0.25", "Coma: 0,25"])
        date_format = c.selectbox("Formato de fechas del CSV", ["AAAA-MM-DD", "DD/MM/AAAA"])
        uploaded = st.file_uploader("Selecciona tu archivo CSV", type="csv", max_upload_size=5, key="operational_csv")
        complete_days = _history_confirmation(kind, "csv_complete_days")
        if uploaded:
            try:
                delimiter = {"Automático": "auto", "Coma": ",", "Punto y coma": ";", "Tabulación": "\t"}[separator]
                raw = read_csv(uploaded.getvalue(), delimiter)
                st.write(f"Archivo leído: **{len(raw)} filas**. Asocia las columnas antes de validar.")
                _show(raw.head(10))
                suggested = suggest_mapping(raw, kind)
                mapping = {}
                for field in SCHEMAS[kind]+(["no_atendidas"] if kind == "ventas_historicas" else []):
                    options = [None]+raw.columns.tolist()
                    mapping[field] = st.selectbox(LABELS[field], options,
                        index=options.index(suggested.get(field)),
                        format_func=lambda value: "Sin asociar" if value is None else value,
                        key=f"mapping_{kind}_{hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]}_{field}")
                prepared = prepare(raw, kind, mapping, decimal="." if decimal_label.startswith("Punto") else ",", date_format=date_format)
                _preview_and_save(service, kind, prepared, uploaded.name, complete_days, "csv")
            except (ValueError, UnicodeError, TypeError) as exc:
                st.error(str(exc))
        else:
            st.info("Selecciona un solo CSV del tipo elegido. No es obligatorio tener los seis archivos.")
    with saved:
        category = st.selectbox("Información guardada", ["Insumos", "Platos", "Recetas", "Inventario", "Ventas históricas", "Importaciones"])
        frame = {"Insumos": lambda: service.ingredients(include_inactive=True), "Platos": lambda: service.dishes(include_inactive=True),
                 "Inventario": service.lots, "Ventas históricas": service.imported_sales, "Importaciones": service.imports,
                 "Recetas": lambda: service._frame("SELECT d.name plato,i.name insumo,r.quantity cantidad,i.unit unidad "
                                                  "FROM recipes r JOIN dishes d ON d.id=r.dish_id JOIN ingredients i ON i.id=r.ingredient_id")}[category]()
        if frame.empty:
            st.info("Todavía no hay registros de este tipo.")
        else:
            _show(frame)
            st.download_button("Descargar estos registros", frame.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"configuracion_{category.lower().replace(' ', '_')}.csv", mime="text/csv")
        st.caption("Las importaciones son completas: si una fila falla, no se guarda ninguna. "
                   "Repetir el mismo contenido no duplica registros. Conserva también tu respaldo SQLite.")
