"""Local restaurant administration, backed by durable domain services."""

import os
import tempfile
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

from restaurante.access import is_public_demo, require_access
from restaurante.evaluation import rolling_evaluation
from restaurante.forecast import forecast_demand, purchase_plan
from restaurante.presentation import brand, context_bar, load_styles, note, page_header, welcome
from restaurante.reports import operation_report, printable_report
from restaurante.seed import seed_demo
from restaurante.service import RestaurantService, business_today

st.set_page_config(
    page_title="Mise · Gestión de restaurante", page_icon=":material/restaurant:", layout="wide"
)
load_styles()

LABELS = {
    "id": "Registro",
    "ingredient_id": "Código de insumo",
    "name": "Nombre",
    "unit": "Unidad",
    "cost": "Costo (S/)",
    "pack_size": "Presentación de compra",
    "shelf_life_days": "Vida útil (días)",
    "safety_stock": "Stock de seguridad",
    "active": "Activo",
    "price": "Precio (S/)",
    "quantity": "Cantidad",
    "available": "Disponible",
    "expired": "Vencido",
    "remaining": "Saldo",
    "unit_cost": "Costo unitario (S/)",
    "received_on": "Recepción",
    "expires_on": "Vencimiento",
    "sold_on": "Fecha de venta",
    "total": "Total (S/)",
    "portions": "Porciones",
    "reason": "Motivo",
    "occurred_on": "Fecha",
    "date": "Fecha",
    "predicted": "Demanda prevista",
    "method": "Método",
    "history_days": "Días de historial",
    "demand": "Demanda prevista",
    "eligible_stock": "Stock aprovechable",
    "safety": "Reserva",
    "suggested_quantity": "Compra sugerida",
    "estimated_cost": "Costo estimado (S/)",
    "closing_stock": "Saldo previsto",
    "expired_quantity": "Vencimiento previsto",
    "missing_days": "Días sin datos completos",
    "order_on": "Pedir a más tardar",
    "expected": "Stock esperado",
    "counted": "Stock contado",
    "day": "Fecha",
    "status": "Estado",
    "origin": "Origen",
    "observations": "Observaciones evaluadas",
    "strategy": "Estrategia",
    "mae": "MAE",
    "rmse": "RMSE",
    "bias": "Sesgo (previsto − real)",
    "wape_percent": "WAPE (%)",
    "mape_percent": "MAPE (%) sin ceros",
    "mape_excluded_zeros": "Ceros excluidos del MAPE",
    "is_open": "Día de atención",
    "created_at": "Fecha de cierre (UTC)",
    "adjustment_id": "Ajuste",
}


def table(frame, filename=None):
    """Keep presentation and exported labels readable without altering service data."""
    if frame.empty:
        st.info("Aún no hay registros para mostrar.")
        return
    display = frame.rename(columns=LABELS)
    if "Estado" in display:
        display["Estado"] = display["Estado"].replace(
            {"complete": "Jornada completa", "closed": "No hubo atención"})
    monetary = {"cost", "unit_cost", "price", "total", "estimated_cost"}
    quantities = {
        "quantity",
        "available",
        "expired",
        "remaining",
        "safety_stock",
        "pack_size",
        "predicted",
        "demand",
        "eligible_stock",
        "safety",
        "suggested_quantity",
        "closing_stock",
        "expired_quantity",
    }
    config = {
        LABELS.get(column, column): st.column_config.NumberColumn(format="%.2f")
        for column in frame.columns
        if column in monetary
    }
    config.update(
        {
            LABELS.get(column, column): st.column_config.NumberColumn(format="%.3f")
            for column in frame.columns
            if column in quantities
        }
    )
    st.dataframe(display, hide_index=True, width="stretch", column_config=config,
                 height=min(420, 36 * len(display) + 40))
    if filename:
        st.download_button(
            "Descargar tabla",
            display.to_csv(index=False).encode("utf-8-sig"),
            file_name=filename,
            mime="text/csv",
            icon=":material/download:",
            key=f"csv_{filename}",
        )


def request_key(operation):
    key = f"request_{st.session_state['mode']}_{operation}"
    if key not in st.session_state:
        st.session_state[key] = str(uuid4())
    return st.session_state[key]


def complete(message, operation=None):
    if operation:
        st.session_state.pop(f"request_{st.session_state['mode']}_{operation}", None)
    st.session_state["flash"] = message
    st.rerun()


def item_label(item_id, frame):
    row = frame.loc[frame["id"] == item_id].iloc[0]
    return str(row["name"]) + (" · inactivo" if not row.get("active", True) else "")


def go_to(page):
    st.session_state["page"] = page


def dashboard(service, today):
    page_header("VISTA GENERAL", "Tu restaurante, al día",
                "Lo que tienes, lo que vendes y lo que necesita atención antes del próximo servicio.")
    with st.expander("Guía de inicio: configura tu restaurante", expanded=service.ingredients().empty):
        st.markdown(
            "1. **Catálogo → Insumos:** registra la unidad y presentación de compra.\n"
            "2. **Platos y Recetas:** indica insumos en peso bruto por porción. "
            "Ejemplo: 200 gramos se registran como 0.200 kg.\n"
            "3. **Compras:** ingresa existencias y sus vencimientos.\n"
            "4. **Ventas:** registra platos vendidos y pedidos no atendidos.\n"
            "5. **Cierre diario:** confirma que terminaste de registrar la jornada.\n"
            "6. **Plan de compras:** revisa cantidades, fechas y limitaciones."
        )
    stock = service.stock(today)
    sales = service.sales()
    todays = sales[pd.to_datetime(sales["sold_on"]).dt.date == today] if not sales.empty else sales
    critical = stock[stock["available"] <= stock["safety_stock"]] if not stock.empty else stock
    a, b, c = st.columns(3)
    a.metric("Ventas de hoy", f"S/ {todays['total'].sum():,.2f}" if not todays.empty else "S/ 0.00")
    b.metric(
        "Valor estimado del stock",
        f"S/ {(stock['available'] * stock['cost']).sum():,.2f}" if not stock.empty else "S/ 0.00",
    )
    c.metric("Insumos por reponer", len(critical))
    st.subheader("¿Qué necesitas hacer?")
    action_columns = st.columns(4)
    for column, label, target, icon in zip(
        action_columns,
        ["Nueva compra", "Registrar venta", "Revisar inventario", "Preparar compra"],
        ["Compras", "Ventas", "Stock y mermas", "Plan de compras"],
        [":material/add_shopping_cart:", ":material/point_of_sale:",
         ":material/inventory_2:", ":material/query_stats:"], strict=True,
    ):
        column.button(label, on_click=go_to, args=(target,), icon=icon, width="stretch")
    st.write("")
    if stock.empty:
        st.info(
            "Comienza en Catálogo: registra tus insumos y platos. Luego ingresa una compra para disponer de stock."
        )
    else:
        left, right = st.columns([1.2, 1])
        with left:
            with st.container(border=True):
                st.subheader("Por reponer")
                st.caption("Insumos en su reserva mínima o por debajo de ella.")
                if critical.empty:
                    st.success("Tus insumos están por encima de su stock de seguridad.")
                else:
                    table(critical[["name", "unit", "available", "safety_stock"]])
        with right:
            with st.container(border=True):
                st.subheader("Vence pronto")
                st.caption("Lotes utilizables que vencen en los próximos tres días.")
                lots = service.lots()
                if not lots.empty:
                    exp = pd.to_datetime(lots["expires_on"]).dt.date
                    near = lots[(lots["remaining"] > 0) & (exp >= today)
                                & (exp <= today + timedelta(days=3))]
                    if near.empty:
                        st.caption("No tienes lotes próximos a vencer.")
                    else:
                        table(near[["name", "remaining", "unit", "expires_on"]])
                else:
                    st.caption("Tus lotes aparecerán al registrar la primera compra.")
    st.subheader("Últimas ventas")
    table(sales.head(10), "ventas.csv")
    st.button("Ver reportes por fecha", icon=":material/assessment:",
              on_click=go_to, args=("Reportes",))


def catalog(service):
    page_header("CONFIGURACIÓN DE COCINA", "Catálogo de cocina",
                "Empieza por tus insumos, crea los platos y conecta ambos con una receta.")
    ingredients_tab, dishes_tab, recipe_tab = st.tabs(["Insumos", "Platos", "Recetas"])
    all_ingredients = service.ingredients(include_inactive=True)
    all_dishes = service.dishes(include_inactive=True)
    with ingredients_tab:
        options = [None] + all_ingredients["id"].tolist()
        selected = st.selectbox(
            "Insumo a editar",
            options,
            format_func=lambda x: "Nuevo insumo" if x is None else item_label(x, all_ingredients),
            key="ingredient_edit",
        )
        row = (
            all_ingredients.loc[all_ingredients["id"] == selected].iloc[0]
            if selected is not None
            else {}
        )
        with st.form(f"ingredient_form_{selected}"):
            st.subheader("Datos del insumo")
            a, b = st.columns([2, 1])
            name = a.text_input("Nombre del insumo", value=row.get("name", ""))
            units = ["kg", "g", "L", "ml", "unidad"]
            current_unit = row.get("unit", "kg")
            if current_unit not in units:
                units.append(current_unit)
            unit = b.selectbox("Unidad de inventario", units, index=units.index(current_unit))
            a, b, c = st.columns(3)
            cost = a.number_input(
                "Costo de referencia por unidad (S/)",
                min_value=0.0,
                value=float(row.get("cost", 0)),
                step=0.5,
            )
            pack = b.number_input(
                "Cantidad por presentación de compra",
                min_value=0.001,
                value=float(row.get("pack_size", 1)),
                step=0.5,
            )
            shelf = c.number_input(
                "Vida útil en días", min_value=1, value=int(row.get("shelf_life_days", 3)), step=1
            )
            safety = st.number_input(
                "Stock de seguridad (unidad de inventario)",
                min_value=0.0,
                value=float(row.get("safety_stock", 0)),
                step=0.5,
            )
            active = st.checkbox("Insumo activo", value=bool(row.get("active", True)))
            st.caption(
                "Mantén la misma unidad en compras y recetas. Los registros anteriores se conservan al desactivar."
            )
            st.caption(
                "Ejemplos: saco de arroz de 50 kg → presentación 50; botella de 900 ml "
                "con inventario en L → presentación 0.9. La vida útil incluye el día de recepción "
                "y depende de las condiciones reales de conservación."
            )
            submitted = st.form_submit_button(
                "Guardar insumo", type="primary", icon=":material/save:"
            )
        if submitted:
            try:
                item_id = service.save_ingredient(
                    name, unit, cost, pack, shelf, safety, ingredient_id=selected
                )
                service.set_ingredient_active(item_id, active)
                complete("Insumo guardado.")
            except ValueError as error:
                st.error(str(error))
        table(all_ingredients, "insumos.csv")
    with dishes_tab:
        selected = st.selectbox(
            "Plato a editar",
            [None] + all_dishes["id"].tolist(),
            format_func=lambda x: "Nuevo plato" if x is None else item_label(x, all_dishes),
            key="dish_edit",
        )
        row = all_dishes.loc[all_dishes["id"] == selected].iloc[0] if selected is not None else {}
        with st.form(f"dish_form_{selected}"):
            st.subheader("Datos del plato")
            name = st.text_input("Nombre del plato", value=row.get("name", ""))
            price = st.number_input(
                "Precio de venta (S/)", min_value=0.0, value=float(row.get("price", 0)), step=1.0
            )
            active = st.checkbox("Plato activo", value=bool(row.get("active", True)))
            submitted = st.form_submit_button(
                "Guardar plato", type="primary", icon=":material/save:"
            )
        if submitted:
            try:
                dish_id = service.save_dish(name, price, dish_id=selected)
                service.set_dish_active(dish_id, active)
                complete("Plato guardado. Define su receta para registrar ventas.")
            except ValueError as error:
                st.error(str(error))
        table(all_dishes, "platos.csv")
    with recipe_tab:
        if all_dishes.empty or all_ingredients.empty:
            st.info("Registra al menos un plato y un insumo para crear una receta.")
        else:
            dish_id = st.selectbox(
                "Receta del plato",
                all_dishes["id"].tolist(),
                format_func=lambda x: item_label(x, all_dishes),
                key="recipe_dish",
            )
            existing = service.recipe(dish_id)
            quantities = dict(zip(existing["ingredient_id"], existing["quantity"]))
            st.caption(
                "Cantidades por una porción. Deja en cero los insumos que no forman parte del plato."
            )
            st.info(
                "Usa peso bruto de almacén: incluye la cantidad necesaria antes de pelar o limpiar. "
                "No vuelvas a registrar esa pérdida habitual como merma. Este flujo descuenta "
                "insumos por venta; las preparaciones por lotes aún requieren control separado."
            )
            with st.form(f"recipe_form_{dish_id}"):
                st.subheader("Insumos por porción")
                values = {}
                for ingredient in all_ingredients.itertuples():
                    values[ingredient.id] = st.number_input(
                        f"{ingredient.name} ({ingredient.unit})"
                        + (" · inactivo" if not ingredient.active else ""),
                        min_value=0.0,
                        value=float(quantities.get(ingredient.id, 0)),
                        step=0.01,
                        key=f"recipe_{dish_id}_{ingredient.id}",
                    )
                submitted = st.form_submit_button(
                    "Guardar receta", type="primary", icon=":material/save:"
                )
            if submitted:
                try:
                    service.set_recipe(dish_id, {i: q for i, q in values.items() if q > 0})
                    complete(
                        "Receta guardada. Las ventas anteriores conservan su consumo original."
                    )
                except ValueError as error:
                    st.error(str(error))


def purchases(service, today):
    page_header("ENTRADAS DE INVENTARIO", "Compras recibidas",
                "Registra lo que llegó a cocina. El stock se actualiza al guardar la recepción.")
    ingredients = service.ingredients()
    if ingredients.empty:
        st.info("Primero registra un insumo activo en Catálogo.")
    else:
        ingredient_id = st.selectbox(
            "Insumo recibido",
            ingredients["id"].tolist(),
            format_func=lambda x: item_label(x, ingredients),
            key="purchase_ingredient",
        )
        ingredient = ingredients.loc[ingredients["id"] == ingredient_id].iloc[0]
        input_mode = st.radio("Ingresar cantidad como", ["Unidad de inventario", "Presentaciones"])
        with st.form(f"purchase_form_{ingredient_id}"):
            st.subheader("Detalle de la recepción")
            a, b = st.columns(2)
            quantity = a.number_input(
                (f"Cantidad recibida ({ingredient['unit']})" if input_mode == "Unidad de inventario"
                 else "Número de presentaciones"), min_value=0.001, value=1.0, step=0.5
            )
            cost = b.number_input(
                ("Costo unitario de esta compra (S/)" if input_mode == "Unidad de inventario"
                 else "Costo por presentación (S/)"),
                min_value=0.0,
                value=float(ingredient["cost"]) * (
                    float(ingredient["pack_size"]) if input_mode == "Presentaciones" else 1),
                step=0.5,
            )
            received = a.date_input("Fecha de recepción", value=today, max_value=today, format="DD/MM/YYYY")
            expires = b.date_input(
                "Fecha de vencimiento", format="DD/MM/YYYY",
                value=today + timedelta(days=int(ingredient["shelf_life_days"]) - 1),
            )
            st.caption("El lote puede utilizarse hasta su fecha de vencimiento inclusive.")
            st.caption(
                f"Cada presentación contiene {ingredient['pack_size']:g} {ingredient['unit']}. "
                "Revisa la fecha real del producto y su conservación."
            )
            submitted = st.form_submit_button(
                "Registrar compra", type="primary", icon=":material/add_shopping_cart:"
            )
        if submitted:
            try:
                if input_mode == "Presentaciones":
                    quantity *= float(ingredient["pack_size"])
                    cost /= float(ingredient["pack_size"])
                service.receive_purchase(
                    ingredient_id, quantity, cost, received, expires, request_key("purchase")
                )
                complete("Compra recibida. El stock ya está actualizado.", "purchase")
            except ValueError as error:
                st.error(str(error))
    st.subheader("Historial de compras")
    table(service.purchases(), "compras.csv")


def sales(service, today):
    page_header("SALIDAS DE INVENTARIO", "Registrar ventas",
                "Elige un plato y sus porciones. La receta calcula el descuento de insumos.")
    dishes = service.dishes()
    if dishes.empty:
        st.info("Registra un plato y su receta en Catálogo antes de vender.")
    else:
        dish_id = st.selectbox(
            "Plato vendido",
            dishes["id"].tolist(),
            format_func=lambda x: item_label(x, dishes),
            key="sale_dish",
        )
        dish = dishes.loc[dishes["id"] == dish_id].iloc[0]
        recipe = service.recipe(dish_id)
        if recipe.empty:
            st.warning("Este plato aún no tiene receta. Complétala en Catálogo → Recetas.")
        with st.form("sale_form"):
            st.subheader("Detalle de la venta")
            a, b = st.columns(2)
            portions = a.number_input("Porciones vendidas", min_value=1, value=1, step=1)
            sold_on = b.date_input("Fecha de venta", value=today, max_value=today, format="DD/MM/YYYY")
            st.caption(
                f"Precio por porción: S/ {dish['price']:,.2f}. Se utilizan primero los lotes que vencen antes (PVPS)."
            )
            submitted = st.form_submit_button(
                "Registrar venta",
                type="primary",
                icon=":material/point_of_sale:",
                disabled=recipe.empty,
            )
        if submitted:
            try:
                sale_id = service.record_sale({dish_id: portions}, sold_on, request_key("sale"))
                complete(
                    f"Venta #{sale_id} registrada. Se descontaron los insumos de la receta.", "sale"
                )
            except ValueError as error:
                st.error(str(error))
    st.subheader("Historial de ventas")
    table(service.sales(), "ventas.csv")
    if not dishes.empty:
        with st.expander("Registrar un pedido que no pudiste atender"):
            st.caption("Solo pedidos reales rechazados por falta de stock. No registra ingresos ni descuenta insumos.")
            with st.form("unmet_form"):
                lost_dish = st.selectbox("Plato solicitado", dishes["id"].tolist(),
                                        format_func=lambda x: item_label(x, dishes))
                lost_portions = st.number_input("Porciones no atendidas", min_value=1, step=1)
                lost_day = st.date_input("Fecha del pedido", value=today, max_value=today, format="DD/MM/YYYY")
                reason = st.text_input("Insumo faltante o motivo")
                save_lost = st.form_submit_button("Guardar pedido no atendido")
            if save_lost:
                try:
                    service.record_unmet(lost_dish, lost_portions, lost_day, reason,
                                         request_key("unmet"))
                    complete("Pedido no atendido guardado.", "unmet")
                except ValueError as error:
                    st.error(str(error))
            table(service.unmet(), "pedidos_no_atendidos.csv")


def inventory(service, today):
    page_header("CONTROL DE INSUMOS", "Stock y mermas",
        "El disponible excluye los lotes vencidos. Registra pérdidas para mantener tu inventario al día."
    )
    stock = service.stock(today)
    if not stock.empty:
        a, b, c = st.columns(3)
        a.metric("Insumos registrados", len(stock))
        b.metric("Insumos sin stock", int(stock.available.le(0).sum()))
        c.metric("Insumos con saldo vencido", int(stock.expired.gt(0).sum()))
    st.subheader("Existencias actuales")
    query = st.text_input("Buscar insumo", placeholder="Ej.: arroz, pollo o aceite")
    visible_stock = stock[stock["name"].str.contains(query, case=False, regex=False)]
    table(visible_stock, "stock.csv")
    with st.expander("Ver lotes y vencimientos"):
        table(service.lots(), "lotes.csv")
    st.subheader("Registrar una merma")
    ingredients = service.ingredients(include_inactive=True)
    if not ingredients.empty:
        ingredient_id = st.selectbox(
            "Insumo con merma",
            ingredients["id"].tolist(),
            format_func=lambda x: item_label(x, ingredients),
            key="waste_ingredient",
        )
        row = ingredients.loc[ingredients["id"] == ingredient_id].iloc[0]
        with st.form("waste_form"):
            a, b = st.columns(2)
            quantity = a.number_input(
                f"Cantidad perdida ({row['unit']})", min_value=0.001, value=0.1, step=0.1
            )
            occurred = b.date_input("Fecha de merma", value=today, max_value=today, format="DD/MM/YYYY")
            reason = st.text_input(
                "Motivo de la merma", placeholder="Ej.: deterioro o caída durante la preparación"
            )
            submitted = st.form_submit_button("Registrar merma", icon=":material/remove_circle:")
        if submitted:
            try:
                service.record_waste(
                    ingredient_id, quantity, reason, occurred, request_key("waste")
                )
                complete("Merma registrada. El stock ya está actualizado.", "waste")
            except ValueError as error:
                st.error(str(error))
    st.subheader("Lotes vencidos")
    st.caption(
        "Retira del inventario los saldos vencidos y deja constancia de su costo como merma."
    )
    if st.button("Procesar vencimientos de hoy", icon=":material/event_busy:"):
        try:
            service.expire_stock(today)
            complete("Vencimientos procesados. Consulta el historial de mermas.")
        except ValueError as error:
            st.error(str(error))
    st.subheader("Historial de mermas")
    table(service.waste(), "mermas.csv")
    if not ingredients.empty:
        with st.expander("Corregir stock mediante conteo físico"):
            st.caption(
                "Cuenta solo producto utilizable. Una diferencia negativa queda como merma; "
                "una positiva crea un lote de ajuste al costo de referencia. Conserva su motivo."
            )
            with st.form("count_form"):
                counted_id = st.selectbox("Insumo contado", ingredients["id"].tolist(),
                                         format_func=lambda x: item_label(x, ingredients))
                counted = st.number_input("Cantidad utilizable contada (unidad de inventario)",
                                          min_value=0.0, step=0.1)
                count_reason = st.text_input("Motivo del ajuste")
                count_expiry = st.date_input("Vencimiento del excedente encontrado", value=today, format="DD/MM/YYYY")
                confirm = st.checkbox("Confirmo que revisé el conteo físico")
                count_save = st.form_submit_button("Guardar ajuste de inventario")
            if count_save:
                if not confirm:
                    st.error("Confirma el conteo antes de guardar.")
                else:
                    try:
                        service.adjust_stock(counted_id, counted, today, count_reason,
                                             count_expiry, request_key("adjustment"))
                        complete("Conteo registrado con trazabilidad.", "adjustment")
                    except ValueError as error:
                        st.error(str(error))
            table(service.adjustments(), "ajustes.csv")


def closing(service, today):
    page_header("AL TERMINAR EL SERVICIO", "Cierre diario",
        "Cierra después de registrar todas las compras, ventas, pedidos no atendidos y mermas. "
        "Una jornada completa mejora la información de tu próximo plan de compras."
    )
    a, b, c = st.columns(3)
    for column, title, description in zip(
        [a, b, c], ["01 · Revisa", "02 · Confirma", "03 · Planifica"],
        ["Verifica compras, ventas y pérdidas.", "Marca la jornada como completa o sin apertura.",
         "Consulta las compras para el próximo servicio."], strict=True,
    ):
        with column:
            note(title, description)
    st.warning(
        "El cierre bloquea nuevos movimientos de esa fecha y fechas anteriores. "
        "Registra primero las jornadas antiguas pendientes, en orden cronológico."
    )
    with st.form("close_day"):
        st.subheader("Confirmación de jornada")
        day = st.date_input("Jornada a cerrar", value=today, max_value=today, format="DD/MM/YYYY")
        state = st.radio("Estado de la jornada", ["Atendimos y el registro está completo",
                                                   "No abrimos el restaurante"])
        confirm = st.checkbox("He revisado los registros y confirmo el cierre")
        submitted = st.form_submit_button("Cerrar jornada", type="primary")
    if submitted:
        if not confirm:
            st.error("Revisa y confirma el cierre.")
        else:
            try:
                service.close_day(day, "complete" if state.startswith("Atendimos") else "closed")
                complete("Jornada cerrada. El historial de planificación se actualizó.")
            except ValueError as error:
                st.error(str(error))
    table(service.closures(), "cierres.csv")


def planning(service, today):
    page_header("PRÓXIMOS SERVICIOS", "Planifica tus compras",
                "Revisa qué insumos necesitarás, cuánto comprar y cuándo hacer el pedido.")
    ingredients = service.ingredients()
    if ingredients.empty:
        st.info("Registra tus insumos y ventas para comenzar a planificar.")
        return
    with st.container(border=True):
        st.subheader("Prepara tu plan")
        a, b, c = st.columns(3)
        horizon = a.slider("Días a planificar", 1, 7, 7)
        lead = b.number_input("Plazo de entrega del proveedor (días)",
                              min_value=0, max_value=30, value=0,
                              help="0: compras y recibes el mismo día. 1: pide el día anterior.")
        safety = c.number_input(
            "Multiplicador del stock de seguridad",
            min_value=0.0, max_value=5.0, value=1.0, step=0.25,
            help="1 mantiene la reserva de Catálogo; 0 planifica sin reserva adicional.",
        )
        day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        attention = st.multiselect("Días habituales de atención", day_names, default=day_names)
    history = service.forecast_history()
    if history.empty:
        st.warning(
            "Aún no hay historial de jornadas completas. Las sugerencias solo pueden cubrir tu "
            "stock de seguridad; registra ventas y confirma el Cierre diario."
        )
    closures = service.closures()
    today_closed = not closures.empty and today.isoformat() in closures["day"].tolist()
    if not today_closed:
        st.warning(
            "La jornada de hoy sigue abierta: el stock aún puede cambiar. Este plan es preliminar. "
            "Ciérrala después del servicio para planificar con el saldo final."
        )
    origin = today + timedelta(days=1)
    predictions = forecast_demand(history, ingredients, origin, horizon=horizon,
                                  operating_weekdays=[day_names.index(d) for d in attention])
    if not predictions.empty and predictions["missing_days"].max() > 0:
        st.warning("Hay huecos en el historial. Se usan observaciones conocidas; los rezagos del "
                   "modelo arrastran el último dato disponible. Revisa la vigencia del historial.")
    plan = purchase_plan(predictions, service.lots(), ingredients, safety_factor=safety,
                         lead_time_days=int(lead))
    st.subheader("Compra sugerida por día")
    st.caption(
        "Considera vencimientos, consumo previsto, reserva y presentaciones de compra. Las cantidades de días posteriores suponen que recibiste las compras sugeridas antes de cada servicio."
    )
    summary_columns = ["order_on", "date", "name", "suggested_quantity", "unit", "estimated_cost"]
    planned_purchases = plan[plan["suggested_quantity"] > 0][summary_columns]
    a, b, c = st.columns(3)
    a.metric("Compra estimada para el periodo", f"S/ {plan['estimated_cost'].sum():,.2f}")
    b.metric("Insumos para comprar", int(plan.loc[plan.suggested_quantity.gt(0), "ingredient_id"].nunique()))
    next_order = (pd.to_datetime(planned_purchases.order_on.min()).strftime("%d/%m/%Y")
                  if not planned_purchases.empty else "—")
    c.metric("Próximo pedido", next_order)
    if planned_purchases.empty:
        if history.empty or predictions["history_days"].eq(0).any():
            st.warning("No hay información suficiente para asegurar que el stock cubra la demanda.")
        else:
            st.info("No se sugieren compras bajo los supuestos y datos disponibles.")
    else:
        if (planned_purchases["order_on"] < today.isoformat()).any():
            st.error("Parte del plan exige pedidos en fechas pasadas. Revisa entrega urgente, "
                     "stock o proveedor: la disponibilidad de esos insumos no está garantizada.")
        selected_day = st.selectbox("Mostrar compras para", ["Todo el periodo"]
                                    + sorted(planned_purchases["date"].unique().tolist()))
        shown = planned_purchases if selected_day == "Todo el periodo" else \
            planned_purchases[planned_purchases["date"] == selected_day]
        st.caption("Cada fila indica cuánto recibir ese día. No sumes kg y litros entre insumos. "
                   "La descarga respeta el filtro seleccionado.")
        table(shown, "plan_de_compras.csv")
    with st.expander("Cómo se calcula: demanda, stock y vencimientos"):
        detail_columns = summary_columns + [
            "demand",
            "eligible_stock",
            "safety",
            "closing_stock",
            "expired_quantity",
        ]
        table(plan[detail_columns], "detalle_plan_de_compras.csv")
    note("De la sugerencia a tu inventario",
         "Demanda prevista + reserva − stock utilizable, redondeado a la presentación de compra. "
         "Después de comprar, registra solo lo que realmente recibiste en Compras.")
    st.subheader("Pronóstico de consumo")
    if not predictions.empty:
        named = predictions.merge(
            ingredients[["id", "name", "unit"]], left_on="ingredient_id", right_on="id", how="left"
        ).drop(columns="id")
        methods = ", ".join(sorted(set(named["method"].astype(str))))
        st.caption(
            f"Método utilizado: {methods}. No se garantiza una precisión hasta evaluar resultados con datos de tu restaurante."
        )
        ingredient_id = st.selectbox(
            "Insumo a visualizar",
            ingredients["id"].tolist(),
            format_func=lambda x: item_label(x, ingredients),
            key="forecast_ingredient",
        )
        series = named[named["ingredient_id"] == ingredient_id]
        st.line_chart(
            series,
            x="date",
            y="predicted",
            color="#087f8c",
            x_label="Fecha",
            y_label=f"Demanda ({ingredients.loc[ingredients['id'] == ingredient_id, 'unit'].iloc[0]})",
        )
        with st.expander("Ver detalle y método"):
            table(named, "pronosticos.csv")
    with st.expander("Evaluación temporal del pronóstico"):
        st.caption(
            "Compara el método automático con promedio y referencia semanal sobre tres bloques "
            "pasados de siete días. Exige 56 días de entrenamiento por insumo. "
            "Las métricas se calculan por insumo; no se mezclan kg y litros. "
            "MAPE excluye ceros y WAPE queda vacío si la demanda total es cero. "
            "En demostración, los resultados describen únicamente datos sintéticos."
        )
        if st.button("Evaluar con historial disponible"):
            with st.spinner("Comparando pronósticos sin utilizar datos futuros..."):
                summary, detail = rolling_evaluation(history, ingredients)
            if summary.empty:
                st.info("Todavía no hay suficientes jornadas completas para evaluar.")
            else:
                table(summary.merge(ingredients[["id", "name", "unit"]],
                                    left_on="ingredient_id", right_on="id"), "evaluacion.csv")
                table(detail, "predicciones_evaluadas.csv")


def reports(service, today):
    page_header("RESULTADOS DE TU OPERACIÓN", "Reportes claros, decisiones informadas",
                "Elige un periodo y revisa lo registrado en ventas, compras y pérdidas.")
    with st.container(border=True):
        a, b = st.columns(2)
        start = a.date_input("Desde", value=today - timedelta(days=6), max_value=today, format="DD/MM/YYYY")
        end = b.date_input("Hasta", value=today, max_value=today, format="DD/MM/YYYY")
    if start > end:
        st.error("La fecha final debe ser igual o posterior a la inicial.")
        return
    if (end - start).days > 730:
        st.info("Selecciona un periodo de hasta 731 días para consultar el reporte.")
        return
    report = operation_report(service, start, end)
    st.caption(f"Periodo: {start:%d/%m/%Y} al {end:%d/%m/%Y} · Importes en soles (S/)")
    a, b, c = st.columns(3)
    a.metric("Ventas registradas", f"S/ {report['sales_amount']:,.2f}")
    b.metric("Compras recibidas", f"S/ {report['purchase_amount']:,.2f}")
    c.metric("Costo de mermas", f"S/ {report['waste_amount']:,.2f}")
    note("Cómo interpretar estos importes",
         "Las ventas son ingresos registrados y las compras son recepciones valorizadas. "
         "No son una utilidad ni un balance. Las mermas incluyen ajustes de conteo con su motivo.")
    a, b, c = st.columns(3)
    a.metric("Porciones vendidas", report["sold_portions"])
    b.metric("Porciones no atendidas", report["unmet_portions"])
    c.metric("Jornadas completas", report["complete_days"])
    if report["complete_days"] == 0:
        st.warning("No hay jornadas confirmadas completas en este periodo. Los totales reflejan "
                   "lo registrado, pero podrían estar incompletos. Revisa el Cierre diario.")
    if st.session_state["mode"] == "Demostración":
        st.info("El historial sintético sirve para pronosticar; no representa ventas operativas. "
                "Aquí verás las compras de ejemplo y las operaciones que registres en esta sesión.")
    st.download_button("Descargar reporte para imprimir", printable_report(
        report, start, end, st.session_state["mode"], LABELS).encode("utf-8"),
        file_name=f"reporte-mise-{start}-{end}.html", mime="text/html",
        icon=":material/print:")
    st.caption("Abre el archivo descargado en tu navegador y usa Imprimir → Guardar como PDF.")
    overview, movements, glossary = st.tabs(["Resumen del periodo", "Detalle y descargas", "Qué significa cada dato"])
    with overview:
        st.subheader("Ventas registradas por día")
        if report["sales"].empty:
            st.info("Todavía no hay ventas registradas en este periodo. Registra una venta "
                    "en Ventas para consultar su evolución aquí.")
        else:
            st.bar_chart(report["daily"], x="date", y="total", color="#087f8c",
                         x_label="Fecha", y_label="Ventas registradas (S/)")
            st.caption("Un día sin registros aparece con S/ 0; no confirma que el restaurante no atendiera.")
        st.subheader("Mermas por insumo")
        waste = report["waste"]
        if waste.empty:
            st.info("No se registraron mermas en el periodo seleccionado.")
        else:
            grouped = waste.groupby(["name", "unit"], as_index=False)[["quantity", "cost"]].sum()
            table(grouped.sort_values("cost", ascending=False), "mermas_por_insumo.csv")
    with movements:
        category = st.selectbox("Qué deseas revisar", ["Ventas", "Compras", "Mermas", "Pedidos no atendidos", "Cierres"])
        key = {"Ventas": "sales", "Compras": "purchases", "Mermas": "waste",
               "Pedidos no atendidos": "unmet", "Cierres": "closures"}[category]
        st.subheader(category)
        table(report[key], f"reporte_{key}_{start}_{end}.csv")
    with glossary:
        st.markdown(
            "- **Ventas registradas:** suma de los precios guardados al vender.\n"
            "- **Compras recibidas:** cantidad recibida por costo unitario; excluye excedentes de conteo.\n"
            "- **Costo de mermas:** valor del inventario perdido según sus lotes.\n"
            "- **Pedidos no atendidos:** solicitudes reales que no se pudieron servir; no generan ingresos.\n"
            "- **Jornadas completas:** días revisados y confirmados en Cierre diario.\n"
            "- **Pronóstico:** consumo estimado futuro; se consulta en Plan de compras.\n"
            "- **Inventario actual:** disponible hoy; se consulta en Stock y mermas y no es un saldo histórico."
        )


def main():
    if not require_access():
        return
    public_demo = is_public_demo()
    if public_demo and st.session_state.get("mode") not in {None, "Demostración"}:
        st.session_state["mode"] = "Demostración"
    if "mode" not in st.session_state:
        brand()
        welcome()
        left, right = st.columns(2, gap="large")
        with left:
            with st.container(border=True, key="welcome_demo"):
                st.caption("PRIMERA VEZ AQUÍ")
                st.subheader("Prueba con un ejemplo")
                st.write("Conoce el inventario, registra una venta y explora un plan de compras "
                         "con datos de demostración.")
                if st.button("Explorar demostración", type="primary", icon=":material/restaurant:",
                             width="stretch"):
                    st.session_state["mode"] = "Demostración"
                    st.rerun()
        with right:
            with st.container(border=True, key="welcome_own"):
                if public_demo:
                    st.caption("ESPACIO DE PRUEBA")
                    st.subheader("Prueba con tranquilidad")
                    st.write("Cada sesión tiene su propio restaurante de ejemplo. Puedes registrar "
                             "compras y ventas sin cambiar los datos de otros visitantes.")
                    st.info("Demostración gratuita: los registros son temporales. "
                            "Descarga los resultados que necesites conservar.")
                else:
                    st.caption("PARA TU OPERACIÓN")
                    st.subheader("Organiza tu restaurante")
                    st.write("Empieza con tus propios insumos y recetas. Una guía te acompaña "
                             "desde la primera compra.")
                    if st.button("Comenzar mi restaurante", icon=":material/storefront:", width="stretch"):
                        st.session_state["mode"] = "Mi restaurante"
                        st.rerun()
        st.caption(
            "Demostración gratuita · Sesiones de prueba independientes · Moneda: soles (S/)"
            if public_demo else
            "Datos separados por espacio · Uso local para un administrador · Moneda: soles (S/)"
        )
        return
    with st.sidebar:
        brand()
        mode = st.selectbox(
            "Espacio de trabajo",
            ["Demostración"] if public_demo else ["Demostración", "Mi restaurante"],
            index=0 if st.session_state["mode"] == "Demostración" else 1,
            key="workspace_mode",
        )
        if mode != st.session_state["mode"]:
            st.session_state["mode"] = mode
            for key in list(st.session_state):
                if key not in {"mode", "workspace_mode", "access_grant"}:
                    del st.session_state[key]
            st.rerun()
        st.divider()
        page = st.radio(
            "Tu operación",
            ["Resumen", "Catálogo", "Compras", "Ventas", "Stock y mermas", "Cierre diario",
             "Plan de compras", "Reportes"],
            key="page",
        )
        st.divider()
        with st.expander("Ayuda rápida"):
            st.caption("Empieza en Catálogo, registra compras y luego ventas. Al terminar el servicio, "
                       "confirma el Cierre diario y revisa tu Plan de compras.")
            st.caption("La demostración y tu restaurante guardan datos por separado.")
    if public_demo:
        if "demo_directory" not in st.session_state:
            st.session_state["demo_directory"] = tempfile.TemporaryDirectory(prefix="mise-demo-")
        data_dir = Path(st.session_state["demo_directory"].name)
    else:
        data_dir = Path(os.environ.get("RESTAURANTE_DATA_DIR", Path(__file__).parent / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    service = RestaurantService(
        data_dir / ("demo.sqlite3" if mode == "Demostración" else "restaurant.sqlite3")
    )
    today = business_today()
    with st.sidebar:
        st.download_button("Descargar respaldo completo", data=service.backup(),
                           file_name=f"respaldo-{service.db_path.stem}-{today}.sqlite3",
                           mime="application/vnd.sqlite3")
    if mode == "Demostración":
        seed_demo(service, today=today)
    context_bar(mode, today.strftime("%d/%m/%Y"))
    if public_demo:
        st.info("Demostración pública · Tu sesión usa datos de ejemplo separados de otros visitantes. "
                "No ingreses datos reales: los cambios pueden perderse al cerrar la sesión o reiniciar "
                "el servidor. Descarga tus resultados antes de salir.")
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))
    if page == "Catálogo":
        catalog(service)
    else:
        handlers = {
            "Resumen": dashboard,
            "Compras": purchases,
            "Ventas": sales,
            "Stock y mermas": inventory,
            "Cierre diario": closing,
            "Plan de compras": planning,
            "Reportes": reports,
        }
        handlers[page](service, today)


main()
