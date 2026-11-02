"""Local restaurant administration, backed by durable domain services."""

import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

from restaurante.forecast import forecast_demand, purchase_plan
from restaurante.seed import seed_demo
from restaurante.service import RestaurantService, business_today

st.set_page_config(
    page_title="Mise · Gestión de restaurante", page_icon=":material/restaurant:", layout="wide"
)
st.markdown(
    """<style>
    .block-container {max-width:1240px;padding-top:2.5rem;padding-bottom:3rem}
    h1 {letter-spacing:-.035em;font-weight:650}
    h2,h3 {letter-spacing:-.02em}
    [data-testid="stSidebar"] {border-right:1px solid #dedfd3}
    [data-testid="stMetricValue"] {font-variant-numeric:tabular-nums}
    ::selection {background:#d5e8d9;color:#163c2a}
    input,textarea {caret-color:#246146}
    a {text-underline-offset:.2em}
    button:focus-visible {outline:3px solid #ba7931;outline-offset:2px}
    </style>""",
    unsafe_allow_html=True,
)

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
}


def table(frame, filename=None):
    """Keep presentation and exported labels readable without altering service data."""
    if frame.empty:
        st.info("Aún no hay registros para mostrar.")
        return
    display = frame.rename(columns=LABELS)
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
    st.dataframe(display, hide_index=True, width="stretch", column_config=config)
    if filename:
        st.download_button(
            "Descargar CSV",
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


def dashboard(service, today):
    st.title("Tu restaurante, al día")
    st.caption(today.strftime("%d/%m/%Y") + " · Hora de Lima")
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
    st.divider()
    if stock.empty:
        st.info(
            "Comienza en Catálogo: registra tus insumos y platos. Luego ingresa una compra para disponer de stock."
        )
    else:
        left, right = st.columns([1.2, 1])
        with left:
            st.subheader("Atención en cocina")
            if critical.empty:
                st.success("Tus insumos están por encima de su stock de seguridad.")
            else:
                st.warning("Revisa estos insumos antes del siguiente servicio.")
                table(critical[["name", "unit", "available", "safety_stock"]])
        with right:
            st.subheader("Próximos vencimientos")
            lots = service.lots()
            if not lots.empty:
                exp = pd.to_datetime(lots["expires_on"]).dt.date
                near = lots[(lots["remaining"] > 0) & (exp <= today + timedelta(days=3))]
                if near.empty:
                    st.caption("Sin lotes pendientes que venzan en los próximos tres días.")
                else:
                    table(near[["name", "remaining", "unit", "expires_on"]])
            else:
                st.caption("Los lotes aparecerán al registrar tu primera compra.")
    st.subheader("Últimas ventas")
    table(sales.head(10), "ventas.csv")


def catalog(service):
    st.title("Catálogo de cocina")
    st.caption("Define qué vendes y cuánto insumo necesita cada porción.")
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
            with st.form(f"recipe_form_{dish_id}"):
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
    st.title("Compras recibidas")
    st.caption("Ingresa lo que llegó a cocina. Cada recepción conserva su fecha de vencimiento.")
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
        with st.form(f"purchase_form_{ingredient_id}"):
            a, b = st.columns(2)
            quantity = a.number_input(
                f"Cantidad recibida ({ingredient['unit']})", min_value=0.001, value=1.0, step=0.5
            )
            cost = b.number_input(
                "Costo unitario de esta compra (S/)",
                min_value=0.0,
                value=float(ingredient["cost"]),
                step=0.5,
            )
            received = a.date_input("Fecha de recepción", value=today, max_value=today)
            expires = b.date_input(
                "Fecha de vencimiento",
                value=today + timedelta(days=int(ingredient["shelf_life_days"])),
            )
            st.caption("El lote puede utilizarse hasta su fecha de vencimiento inclusive.")
            submitted = st.form_submit_button(
                "Registrar compra", type="primary", icon=":material/add_shopping_cart:"
            )
        if submitted:
            try:
                service.receive_purchase(
                    ingredient_id, quantity, cost, received, expires, request_key("purchase")
                )
                complete("Compra recibida. El stock ya está actualizado.", "purchase")
            except ValueError as error:
                st.error(str(error))
    st.subheader("Historial de compras")
    table(service.purchases(), "compras.csv")


def sales(service, today):
    st.title("Registrar ventas")
    st.caption("Cada venta descuenta automáticamente los insumos de su receta.")
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
            a, b = st.columns(2)
            portions = a.number_input("Porciones vendidas", min_value=1, value=1, step=1)
            sold_on = b.date_input("Fecha de venta", value=today, max_value=today)
            st.caption(
                f"Precio por porción: S/ {dish['price']:,.2f}. Se utilizan primero los lotes recibidos más antiguos que sigan vigentes."
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


def inventory(service, today):
    st.title("Stock y mermas")
    st.caption(
        "El disponible excluye los lotes vencidos. Registra pérdidas para mantener tu inventario al día."
    )
    table(service.stock(today), "stock.csv")
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
            occurred = b.date_input("Fecha de merma", value=today, max_value=today)
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


def planning(service, today):
    st.title("Planifica tus compras")
    st.caption(
        "Una guía para el próximo servicio, basada en el consumo de insumos de tu restaurante."
    )
    st.caption(
        "Los días sin ventas registradas entre el primer consumo y hoy se consideran consumo cero. "
        "Registra cada servicio para que el historial represente tu operación."
    )
    ingredients = service.ingredients()
    if ingredients.empty:
        st.info("Registra tus insumos y ventas para comenzar a planificar.")
        return
    a, b = st.columns(2)
    horizon = a.slider("Días a planificar", 1, 7, 7)
    safety = b.number_input(
        "Multiplicador del stock de seguridad",
        min_value=0.0,
        max_value=5.0,
        value=1.0,
        step=0.25,
        help="1 mantiene la reserva configurada en Catálogo; 0 planifica sin reserva adicional.",
    )
    history = service.demand_history()
    if history.empty:
        st.warning(
            "Aún no hay historial de consumo. Las sugerencias solo pueden cubrir tu stock de seguridad; registra ventas para mejorar el pronóstico."
        )
    origin = today + timedelta(days=1)
    predictions = forecast_demand(history, ingredients, origin, horizon=horizon)
    plan = purchase_plan(predictions, service.lots(), ingredients, safety_factor=safety)
    st.subheader("Compra sugerida por día")
    st.caption(
        "Considera vencimientos, consumo previsto, reserva y presentaciones de compra. Las cantidades de días posteriores suponen que recibiste las compras sugeridas antes de cada servicio."
    )
    st.metric("Compra estimada para el periodo", f"S/ {plan['estimated_cost'].sum():,.2f}")
    summary_columns = ["date", "name", "suggested_quantity", "unit", "estimated_cost"]
    planned_purchases = plan[plan["suggested_quantity"] > 0][summary_columns]
    if planned_purchases.empty:
        st.success(
            "El stock previsto cubre este periodo y la reserva configurada. No se sugieren compras."
        )
    else:
        table(planned_purchases, "plan_de_compras.csv")
    with st.expander("Cómo se calcula: demanda, stock y vencimientos"):
        detail_columns = summary_columns + [
            "demand",
            "eligible_stock",
            "safety",
            "closing_stock",
            "expired_quantity",
        ]
        table(plan[detail_columns], "detalle_plan_de_compras.csv")
    st.info(
        "Estas recomendaciones no registran compras. Confirma lo que realmente recibiste en Compras."
    )
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
            color="#246146",
            x_label="Fecha",
            y_label=f"Demanda ({ingredients.loc[ingredients['id'] == ingredient_id, 'unit'].iloc[0]})",
        )
        with st.expander("Ver detalle y método"):
            table(named, "pronosticos.csv")


def main():
    if "mode" not in st.session_state:
        st.title("Una cocina mejor organizada")
        st.write(
            "Registra tus compras y ventas, cuida tus insumos y prepara la próxima compra con una previsión de demanda."
        )
        st.divider()
        left, right = st.columns(2, gap="large")
        with left:
            st.subheader("Conoce el sistema")
            st.write(
                "Explora un restaurante de ejemplo con platos, recetas, stock e historial sintético. Puedes registrar operaciones sin afectar tus propios datos."
            )
            if st.button("Explorar demostración", type="primary", icon=":material/restaurant:"):
                st.session_state["mode"] = "Demostración"
                st.rerun()
        with right:
            st.subheader("Organiza tu restaurante")
            st.write(
                "Comienza con un espacio vacío. Agrega tus insumos, prepara tus recetas y registra la primera compra."
            )
            if st.button("Comenzar mi restaurante", icon=":material/storefront:"):
                st.session_state["mode"] = "Mi restaurante"
                st.rerun()
        st.caption(
            "Uso local para un administrador. Tus registros se conservan al cerrar la aplicación."
        )
        return
    with st.sidebar:
        st.markdown(":material/restaurant: **Mise · restaurante**")
        st.caption("Menos improvisación. Más control en cocina.")
        mode = st.selectbox(
            "Espacio de trabajo",
            ["Demostración", "Mi restaurante"],
            index=0 if st.session_state["mode"] == "Demostración" else 1,
            key="workspace_mode",
        )
        if mode != st.session_state["mode"]:
            st.session_state["mode"] = mode
            for key in list(st.session_state):
                if key not in {"mode", "workspace_mode"}:
                    del st.session_state[key]
            st.rerun()
        st.divider()
        page = st.radio(
            "Tu operación",
            ["Resumen", "Catálogo", "Compras", "Ventas", "Stock y mermas", "Plan de compras"],
            key="page",
        )
        st.divider()
        st.caption("Cada espacio guarda sus propios registros.")
    data_dir = Path(os.environ.get("RESTAURANTE_DATA_DIR", Path(__file__).parent / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    service = RestaurantService(
        data_dir / ("demo.sqlite3" if mode == "Demostración" else "restaurant.sqlite3")
    )
    today = business_today()
    if mode == "Demostración":
        seed_demo(service, today=today)
        st.warning(
            "Demostración · Datos sintéticos y parámetros de ejemplo. Las operaciones de este espacio se guardan por separado.",
            icon=":material/science:",
        )
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
            "Plan de compras": planning,
        }
        handlers[page](service, today)


main()
