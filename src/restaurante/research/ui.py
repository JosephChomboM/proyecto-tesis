"""Guided research workspace, with bounded imports and no operational database writes."""

import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from restaurante.access import is_public_demo
from restaurante.presentation import note, page_header

from .data import GenerationConfig, bundle_zip, example_tables, generate
from .models import MODEL_NAMES, ExperimentConfig, available_models
from .report import cost_comparison, printable_experiment
from .runner import run_experiment
from .simulation import InventoryConfig
from .validation import aiken_scores, sus_scores

LABELS = {
    "profile": "Perfil", "restaurant": "Restaurante", "dish": "Plato",
    "ingredient": "Insumo", "date": "Fecha", "demand": "Demanda teórica",
    "demand_portions": "Porciones solicitadas", "is_open": "Atención",
    "daily_portions": "Porciones base/día", "weekdays": "Días (lunes=0)",
    "weekend_factor": "Factor fin de semana", "holiday_factor": "Factor feriado",
    "heat_effect": "Efecto por °C sobre 21 °C", "source": "Fuente o supuesto",
    "quantity": "Cantidad cruda/porción", "name": "Nombre", "unit": "Unidad",
    "cost": "Costo por unidad (S/)", "pack_size": "Presentación",
    "shelf_life_days": "Vida útil supuesta (días)", "lead_days": "Plazo (días)",
    "model": "Modelo", "external": "Variables externas", "actual": "Demanda sintética",
    "predicted": "Pronóstico", "origin": "Fecha de emisión", "mae": "MAE",
    "rmse": "RMSE", "bias": "Sesgo", "r2": "R²", "wape_percent": "WAPE (%)",
    "mape_percent": "MAPE (%) sin ceros", "mape_excluded_zeros": "Ceros excluidos",
    "observations": "Observaciones", "policy": "Política", "served": "Cantidad atendida",
    "unmet": "Cantidad no atendida", "stockout": "Insumo-días con quiebre",
    "received": "Cantidad recibida", "expired": "Cantidad vencida",
    "waste_cost": "Merma por vencimiento (S/)", "purchase_cost": "Compras (S/)",
    "initial_stock": "Stock inicial", "final_stock": "Stock final",
    "service_percent": "Nivel de servicio (%)", "waste_percent": "Merma/recepciones (%)",
    "participant": "Participante", "sus": "Puntaje SUS", "item": "Criterio",
    "experts": "Expertos", "mean": "Valoración media", "aiken_v": "V de Aiken",
}


def display(frame):
    result = frame.copy()
    if "model" in result:
        result["model"] = result.model.map(lambda value: MODEL_NAMES.get(value, value))
    if "policy" in result:
        result["policy"] = result.policy.replace({"empirical": "Regla empírica supuesta", "forecast": "Pronóstico seleccionado"})
    st.dataframe(result.rename(columns=LABELS), hide_index=True, width="stretch")


def read_results(content):
    """No extraction, pickle, executable content or unbounded decompression."""
    allowed_csv = {"metrics", "predictions", "decision_predictions", "tuning", "model_status",
                   "inventory_daily", "inventory_summary", "forecast_tests", "forecast_blocks"}
    allowed_json = {"experiment", "inventory_protocol", "environment", "metadata"}
    if len(content) > 20_000_000:
        raise ValueError("El ZIP debe pesar menos de 20 MB.")
    result = {}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if len(archive.infolist()) > 20 or sum(info.file_size for info in archive.infolist()) > 60_000_000:
            raise ValueError("El contenido descomprimido supera el límite permitido.")
        for info in archive.infolist():
            stem, dot, suffix = info.filename.rpartition(".")
            if not dot or "/" in stem or "\\" in stem or stem in result:
                raise ValueError("Estructura de resultados inválida.")
            if suffix == "csv" and stem in allowed_csv:
                payload = archive.read(info)
                try:
                    result[stem] = pd.read_csv(io.BytesIO(payload))
                except pd.errors.EmptyDataError:
                    result[stem] = pd.DataFrame()
            elif suffix == "json" and stem in allowed_json:
                result[stem] = json.loads(archive.read(info))
            else:
                raise ValueError("El ZIP contiene archivos ajenos al formato de resultados.")
    required = {"metrics", "predictions", "inventory_summary", "experiment", "metadata"}
    if not required <= set(result):
        raise ValueError("Faltan archivos de resultados; carga results-SEMILLA.zip, no el dataset.")
    for name, columns in {"metrics": {"model", "external", "profile", "ingredient", "wape_percent"},
                          "predictions": {"date", "model", "external", "profile", "ingredient", "actual", "predicted"},
                          "inventory_summary": {"policy", "profile", "ingredient", "waste_cost", "stockout"}}.items():
        if not columns <= set(result[name]):
            raise ValueError(f"El archivo {name} no tiene las columnas requeridas.")
    if not isinstance(result["experiment"], dict) or not isinstance(result["metadata"], dict):
        raise ValueError("Metadatos inválidos.")
    return result


def generation_tab():
    st.subheader("1. Configura un ejemplo entendible")
    st.write("Cada fila del perfil representa un plato. Define sus recetas e insumos una sola vez; "
             "el sistema genera los días y calcula la necesidad de ingredientes.")
    st.warning("Los valores iniciales son supuestos ilustrativos. No están calibrados ni validados "
               "como representativos de Lima. Las recetas simplificadas no son un menú completo.")
    defaults = example_tables()
    tables = []
    names = ("profiles", "recipes", "ingredients")
    titles = ("Perfiles y platos", "Recetas en cantidades crudas", "Insumos y compras")
    with st.expander("Editar parámetros o cargar tus tres archivos CSV"):
        st.caption("Documenta la fuente o la justificación en cada fila. El código mantiene "
                   "los nombres de columnas del CSV para facilitar la reproducción.")
        for name, title, default in zip(names, titles, defaults, strict=True):
            st.markdown(f"**{title}**")
            uploaded = st.file_uploader(f"Cargar {name}.csv", type="csv", key=f"research_{name}_upload")
            frame = pd.read_csv(uploaded, keep_default_na=False) if uploaded else default
            tables.append(st.data_editor(frame, num_rows="dynamic", hide_index=True, width="stretch",
                                         key=f"research_editor_{name}"))
            st.download_button(f"Descargar plantilla {name}.csv", default.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"{name}.csv", mime="text/csv")
        context_file = st.file_uploader("Contexto opcional: context.csv", type="csv")
        st.caption("Columnas: date, expected_temperature, holiday (0/1), context_source. "
                   "Debe cubrir todo el periodo. Usa temperatura esperada disponible antes de pronosticar. "
                   "Sin archivo: temperatura sintética y feriados nacionales 2024–2025 documentados. "
                   "Otros años requieren su propio contexto para incorporar feriados.")
    profile_options = tables[0]["profile"].dropna().unique().tolist() if "profile" in tables[0] else []
    selected = st.multiselect("Perfiles a generar", profile_options,
                              default=profile_options, key="research_profiles")
    a, b, c = st.columns(3)
    start = a.date_input("Inicio del dataset", date(2024, 1, 1), format="DD/MM/YYYY")
    end = b.date_input("Fin del dataset", date(2025, 12, 31), format="DD/MM/YYYY")
    seed = c.number_input("Semilla reproducible", 0, 4294967295, 42, step=1)
    noise = st.slider("Variación diaria del escenario", 0., .6, .18, .01)
    if st.button("Generar dataset sintético", type="primary", icon=":material/dataset:"):
        p, r, i = tables
        # Filtering recipes follows selection; ingredient catalog stays available for editing.
        if "profile" not in p or "dish" not in p or "dish" not in r:
            raise ValueError("Revisa las columnas de perfiles y recetas.")
        p = p[p.profile.isin(selected)]
        r = r[r.dish.isin(p.dish)]
        context = pd.read_csv(context_file) if context_file else None
        with st.spinner("Generando solicitudes y necesidades por insumo…"):
            st.session_state["research_bundle"] = generate(
                GenerationConfig(str(start), str(end), int(seed), noise), (p, r, i), context)
        st.session_state.pop("research_results", None)
        st.success("Dataset generado. Aún requiere calibración y evaluación de expertos.")
    bundle = st.session_state.get("research_bundle")
    if bundle:
        a, b, c = st.columns(3)
        a.metric("Perfiles", bundle["profiles"].profile.nunique())
        b.metric("Días por serie", bundle["demand"].date.nunique())
        c.metric("Registros insumo-día", len(bundle["demand"]))
        st.download_button("Descargar dataset y configuración (ZIP)", bundle_zip(bundle),
                           file_name=f"dataset-{bundle['metadata']['generation']['seed']}.zip", mime="application/zip")
        profile = st.selectbox("Vista previa del perfil", bundle["demand"].profile.unique())
        subset = bundle["dish_demand"][bundle["dish_demand"].profile == profile]
        st.line_chart(subset.pivot(index="date", columns="dish", values="demand_portions"),
                      y_label="Porciones solicitadas (simuladas)")
        display(subset.head(20))
        st.caption("Demanda potencial: todavía no se ha limitado por stock. Las ventas atendidas se "
                   "determinan después, en la simulación.")


def experiment_tab():
    st.subheader("2. Compara modelos y decisiones de compra")
    note("Prueba final reservada", "Los hiperparámetros y el método ganador se seleccionan con validación. "
         "El periodo de prueba se usa para informar el desempeño final y simular inventario.")
    a, b = st.columns(2)
    train_end = a.date_input("Último día de entrenamiento", date(2025, 5, 31), format="DD/MM/YYYY")
    validation_end = b.date_input("Último día de validación", date(2025, 9, 15), format="DD/MM/YYYY")
    availability = available_models()
    display(pd.DataFrame([{"Modelo": MODEL_NAMES[key], "Disponible aquí": value} for key, value in availability.items()]))
    st.caption("Ingenuo estacional: referencia semanal. RF/XGBoost/LSTM: dos configuraciones por modelo "
               "y variantes con/sin contexto externo. Pronósticos recursivos de siete días.")
    with st.expander("Reglas iguales para ambas políticas de compra"):
        a, b, c = st.columns(3)
        empirical_days = a.number_input("Días previos para la regla empírica", 1, 90, 28)
        safety_days = b.number_input("Reserva en días de demanda media", 0., 7., .2, step=.1)
        initial_days = c.number_input("Inventario inicial en días de demanda", 0., 7., 1., step=.1)
        st.caption("La regla empírica inicial es un supuesto que debe revisarse con administradores. "
                   "La merma del experimento corresponde a insumos vencidos, no comida preparada sobrante.")
    if is_public_demo():
        st.info("En Render gratuito puedes generar datasets y consultar resultados. Ejecuta el entrenamiento "
                "completo en tu computadora y carga aquí el ZIP obtenido.")
    else:
        chosen = st.multiselect("Modelos a ejecutar", list(MODEL_NAMES),
                                default=[key for key in MODEL_NAMES if availability[key]],
                                format_func=lambda key: MODEL_NAMES[key])
        if st.button("Entrenar, evaluar y simular compras", disabled="research_bundle" not in st.session_state):
            message = st.empty()
            with st.spinner("Ejecutando el experimento local. Puede tardar varios minutos…"):
                st.session_state["research_results"] = run_experiment(st.session_state["research_bundle"],
                    ExperimentConfig(str(train_end), str(validation_end), models=tuple(chosen)),
                    InventoryConfig(int(empirical_days), float(safety_days), float(initial_days)),
                    progress=message.info)
            message.success("Experimento terminado. Consulta Resultados y descargas.")
    with st.expander("Cómo ejecutar todo localmente", expanded=is_public_demo()):
        st.code('python -m pip install -e ".[research]"\n'
                'python -m restaurante.research.runner --seeds 42 --output data/research', language="powershell")
        st.caption("Para réplicas usa --seeds 42,43,44,45,46. Las versiones y parámetros quedan en el ZIP. "
                   "Primero valida y fija el generador; no cambies sus reglas buscando confirmar una hipótesis.")
    uploaded = st.file_uploader("Cargar resultados locales: results-SEMILLA.zip", type="zip")
    if uploaded and st.button("Abrir resultados del experimento"):
        st.session_state["research_results"] = read_results(uploaded.getvalue())
        st.success("Resultados cargados. Son un archivo aportado por el usuario; no una certificación de su validez.")


def results_tab():
    st.subheader("3. Entiende y descarga los resultados")
    example = Path(__file__).with_name("example-results.zip")
    if example.exists():
        st.caption("Para conocer los reportes sin entrenar, abre un experimento de ejemplo ya calculado. "
                   "Sus datos y parámetros son ilustrativos, no resultados definitivos de la tesis.")
        if st.button("Ver experimento de ejemplo", icon=":material/assessment:"):
            st.session_state["research_results"] = read_results(example.read_bytes())
    results = st.session_state.get("research_results")
    if not results:
        st.info("Ejecuta un experimento local o carga su ZIP en la pestaña anterior.")
        return
    st.warning("Resultados de un entorno sintético. No demuestran mejoras observadas en un negocio real "
               "ni reemplazan la validación de expertos y usuarios.")
    winner = results["experiment"].get("winner")
    if winner:
        st.success(f"Método seleccionado en validación: {MODEL_NAMES.get(winner['model'], winner['model'])} "
                   f"· {'con' if winner.get('external') else 'sin'} variables externas.")
    st.download_button("Descargar todos los resultados (ZIP)", bundle_zip(results),
                       file_name="results-export.zip", mime="application/zip")
    st.download_button("Descargar informe del experimento para imprimir", printable_experiment(results, LABELS).encode("utf-8"),
                       file_name="informe-experimento.html", mime="text/html")
    st.caption("Abre el informe HTML en el navegador y usa Imprimir → Guardar como PDF.")
    st.markdown("**Precisión por insumo y perfil**")
    display(results["metrics"])
    st.caption("MAE/RMSE: unidades del insumo; menores valores son mejores. WAPE: error absoluto/total demandado. "
               "MAPE excluye demanda cero e informa cuántos ceros excluyó. R² puede ser negativo. "
               "No se suman kilogramos con litros ni se presentan errores de entrenamiento como precisión final.")
    predictions = results["predictions"].copy()
    options = predictions[["profile", "ingredient", "model", "external"]].drop_duplicates().to_records(index=False).tolist()
    if options:
        chosen = st.selectbox("Serie y modelo para revisar", options,
                              format_func=lambda value: f"{value[0]} · {value[1]} · {MODEL_NAMES.get(value[2], value[2])} · externas: {value[3]}")
        profile, ingredient, model, external = chosen
        subset = predictions[(predictions.profile == profile) & (predictions.ingredient == ingredient) &
                             (predictions.model == model) & (predictions.external == external)]
        chart = subset.assign(date=pd.to_datetime(subset.date)).set_index("date")[["actual", "predicted"]]
        st.line_chart(chart.rename(columns={"actual": "Demanda sintética", "predicted": "Pronóstico"}))
    st.markdown("**Impacto simulado en inventario**")
    comparison = cost_comparison(results["inventory_summary"])
    a, b, c = st.columns(3)
    a.metric("Merma con regla empírica", f"S/ {comparison['empirical_waste_cost']:,.2f}")
    b.metric("Merma con pronóstico", f"S/ {comparison['forecast_waste_cost']:,.2f}")
    reduction = comparison["relative_waste_reduction"]
    c.metric("Reducción relativa del costo de merma", f"{reduction:.1f}%" if reduction is not None else "No definida")
    st.caption(f"Quiebres: {comparison['empirical_stockouts']} con regla empírica y "
               f"{comparison['forecast_stockouts']} con pronóstico. Una reducción negativa significa que empeoró. "
               "Este resumen monetario no sustituye el análisis de cantidad de merma por insumo de la hipótesis.")
    display(results["inventory_summary"])
    st.caption("Merma: insumos vencidos. Quiebre: insumo-día con demanda no atendida. Servicio: cantidad "
               "atendida/demandada por insumo; no garantiza que todos los platos puedan prepararse. "
               "El stock final se informa y no se descarta artificialmente al terminar el experimento.")
    st.info("Una ejecución no establece significancia estadística del impacto. El comando con varias semillas "
            "produce comparaciones pareadas por réplica, sin tratar días consecutivos como independientes.")
    with st.expander("Trazabilidad, pruebas y limitaciones"):
        st.json(results["metadata"])
        st.json(results["experiment"])
        if "model_status" in results:
            display(results["model_status"])
        if "forecast_tests" in results:
            display(results["forecast_tests"])
            st.caption("Diebold-Mariano aproximado, pérdida cuadrática y varianza HAC; p exploratorios "
                       "por serie, sin corrección por comparaciones múltiples.")


def human_validation_tab():
    st.subheader("4. Registra las evaluaciones humanas")
    st.write("Obtén consentimiento, usa códigos anónimos y aplica el instrumento acordado en la tesis. "
             "La aplicación calcula puntajes; no genera respuestas de expertos ni participantes.")
    sus_template = pd.DataFrame(columns=["participant"]+[f"q{i}" for i in range(1, 11)])
    aiken_template = pd.DataFrame(columns=["expert", "item", "rating"])
    st.download_button("Plantilla de respuestas SUS", sus_template.to_csv(index=False).encode(),
                       file_name="sus_responses.csv", mime="text/csv")
    st.download_button("Plantilla de valoración de expertos", aiken_template.to_csv(index=False).encode(),
                       file_name="expert_ratings.csv", mime="text/csv")
    st.markdown("**Tareas sugeridas para la prueba de usabilidad**\n\n"
                "1. Registrar una compra en su presentación habitual.\n"
                "2. Registrar las porciones vendidas y cerrar la jornada.\n"
                "3. Identificar un insumo próximo a vencer.\n"
                "4. Explicar cuánto recomienda comprar el sistema y para qué fecha.\n"
                "5. Consultar y descargar un reporte del periodo.")
    st.caption("Registra también si terminó cada tarea, cuánto tardó y qué ayuda necesitó. "
               "Usa una versión española validada de SUS, conservando orden y polaridad de sus 10 ítems.")
    sus_file = st.file_uploader("Respuestas SUS reales (CSV)", type="csv")
    if sus_file:
        scores = sus_scores(pd.read_csv(sus_file))
        display(scores)
        st.metric("SUS promedio (0–100)", f"{scores.sus.mean():.1f}")
        st.caption(f"{len(scores)} participantes. Referencia de la hipótesis: 68; no es un porcentaje de satisfacción.")
        if len(scores) < 5:
            st.warning("El informe contempla al menos cinco administradores o propietarios.")
    expert_file = st.file_uploader("Valoraciones reales de expertos (CSV)", type="csv")
    if expert_file:
        scores = aiken_scores(pd.read_csv(expert_file))
        display(scores)
        st.caption("Escala declarada de 1 a 5. V=(media−1)/4 por criterio; referencia HE1: ≥0.80. "
                   "El informe contempla tres expertos con perfiles complementarios. No se calcula un intervalo de confianza aquí.")
        if scores.experts.min() < 3:
            st.warning("Faltan valoraciones de expertos respecto al protocolo del informe.")


def research_page(service=None, today=None):
    page_header("INVESTIGACIÓN REPRODUCIBLE", "De los datos a la evidencia",
                "Genera un escenario sencillo, compara pronósticos y estudia las compras sin modificar tu inventario.")
    st.caption("Ruta de trabajo: configurar → generar → validar con expertos → experimentar → evaluar con usuarios.")
    tabs = st.tabs(["1 · Dataset", "2 · Experimento", "3 · Resultados", "4 · Expertos y usuarios"])
    for tab, handler in zip(tabs, (generation_tab, experiment_tab, results_tab, human_validation_tab), strict=True):
        with tab:
            try:
                handler()
            except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as exc:
                st.error(f"No se pudo completar la operación: {exc}")
