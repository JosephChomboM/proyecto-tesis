# Estudio reproducible de la tesis

El comando siguiente genera cinco réplicas piloto y treinta definitivas de tres escenarios de restaurante. Usa un protocolo fijo de 2024 a 2025, nueve platos y ocho insumos seleccionados por perfil. Cada réplica incluye 6 579 filas de solicitudes por plato y día y 17 544 filas de necesidad cruda por insumo y día.

```powershell
.venv\Scripts\python -m pip install -e ".[research]"
.venv\Scripts\python -m restaurante.research.study --output data/mi-estudio
.venv\Scripts\python scripts/summarize_study.py --output data/mi-estudio
```

Son supuestos no calibrados con ventas reales ni expertos. Las semillas miden estabilidad computacional bajo las mismas reglas; no representan una muestra de 90 restaurantes. Los pilotos no entran en las estadísticas definitivas. Las treinta semillas se fijaron como presupuesto exploratorio, sin análisis de potencia. No cambiar parámetros o seleccionar semillas buscando confirmar hipótesis.

El protocolo congelado guarda configuración y huellas de código antes del primer entrenamiento. El comando se puede reanudar: verifica las huellas de los archivos completos y no vuelve a entrenarlos. Si cambia la implementación científica o el protocolo debe utilizarse otra carpeta. Un entrenamiento interrumpido sin checkpoint se repite. El procedimiento secuencial es la referencia sencilla; `scripts/run_study_parallel.py` ejecuta las semillas definitivas con procesos independientes tras congelar el protocolo. No ejecutar ambos sobre las mismas semillas simultáneamente.

## Archivos

- `configuracion/`: perfiles, recetas e insumos, con fuente o supuesto en cada fila.
- `protocolo_congelado.json`: reglas, semillas, particiones, modelos y huellas de implementación.
- `pilot/dataset-1001.zip` a `dataset-1005.zip`: pilotos con sus correspondientes resultados y comprobantes.
- `final/dataset-2001.zip` a `dataset-2030.zip`: datasets definitivos.
- `final/results-2001.zip` a `results-2030.zip`: métricas, predicciones, selección y simulación diaria.
- `resumen/`: métricas agregadas y comparaciones pareadas entre semillas, con intervalos bootstrap y p de Wilcoxon. Holm se aplica dentro de cada familia de comparaciones identificada en el nombre de la columna.
- `versiones.json`: bibliotecas de entrenamiento.

## Volver a cargar en la aplicación

1. Entrar en **Investigación → 1 · Dataset**.
2. Abrir **Volver a cargar un dataset de investigación**.
3. Subir el ZIP individual `dataset-2001.zip` y pulsar **Abrir dataset guardado**. No subir el paquete general ni un ZIP de resultados aquí.
4. Para consultar lo ya entrenado, ir a **2 · Experimento**, subir `results-2001.zip` y pulsar **Abrir resultados del experimento**.
5. Consultar **3 · Resultados** y sus descargas.

El ZIP de datos se verifica por estructura, huellas y regeneración con su semilla. Se mantiene separado del inventario operativo. Los registros sintéticos de solicitudes no son ventas reales y no deben importarse como tales en Configuración inicial.

Render gratuito permite consultar y generar datos. El entrenamiento completo se realiza localmente y no requiere contratar servicios. Para reproducir un estudio entregado, usar sus versiones fijadas y el código incluido en su paquete, no asumir que cualquier versión futura del repositorio dará exactamente los mismos resultados.

## Interpretación para el informe

La selección usa validación temporal y nunca el error de prueba. El estudio informa resultados favorables y desfavorables. Merma significa vencimiento de insumo crudo; un quiebre es un insumo día con solicitudes no atendidas. La suma de insumo días no equivale a clientes o platos perdidos.

Los costos y vidas útiles son supuestos constantes. Las recetas cubren insumos seleccionados, sin representar todos los componentes de cocina. El aceite se expresa en kg. La temperatura es una climatología sintética conocida y los feriados corresponden al calendario nacional documentado de 2024 y 2025. No se modelan eventos locales no registrados.

Las métricas y el inventario simulado corresponden a Investigación. El Plan de compras operativo conserva su selector de Random Forest o métodos de respaldo; no cambia automáticamente al XGBoost o LSTM seleccionado en el estudio. La evaluación de esa integración requiere trabajo adicional antes de atribuir efectos del simulador al uso diario del prototipo.

La validación de verosimilitud por expertos y el SUS requieren respuestas humanas reales; no se completan mediante simulación. Si el protocolo de tesis exige calibración previa, este estudio es preliminar y deberá repetirse una vez validado el generador.
