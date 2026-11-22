# Operación sencilla y experimentos de tesis

La pantalla **Investigación** está separada del inventario operativo. Generar datos, entrenar
o simular no crea compras, ventas ni existencias en el restaurante propio.

## Probar desde la aplicación

1. Abre demostración o tu restaurante y selecciona **Investigación** en la barra lateral.
2. En **Dataset**, revisa los perfiles, las recetas y los insumos. Los valores iniciales son
   ejemplos simplificados, sin calibración peruana verificada ni aprobación de expertos.
3. Genera el periodo y descarga el ZIP. Incluye las tres configuraciones, contexto,
   solicitudes de platos, demanda de insumos y metadatos de reproducción.
4. Localmente, ejecuta los modelos en **Experimento**. En Render gratuito genera los datos
   y carga un ZIP de resultados producido en tu computadora. El servidor no entrena redes.
5. En **Resultados**, revisa errores por serie, curvas de demanda/pronóstico, inventario y
   descarga los archivos. En **Expertos y usuarios**, carga las respuestas humanas reales.

**Ver experimento de ejemplo** permite consultar un experimento ya calculado sin entrenar
en Render. Se genera con el comando por defecto, semilla 42 y parámetros ilustrativos;
sus versiones, modelos realmente ejecutados y selección están en los metadatos del ZIP.
No es evidencia definitiva ni incluye evaluaciones humanas.

No hay conexiones pagadas ni consumo de APIs. Las dependencias de investigación son
gratuitas y opcionales; el entrenamiento completo usa CPU local.

## Configuración y fuentes

`profiles.csv`: una fila por plato; perfil, nombre del restaurante, porciones diarias base,
días de atención (lunes=0, domingo=6), multiplicadores de fin de semana/feriado, sensibilidad
al calor y fuente o supuesto. Los nombres de platos deben ser únicos entre perfiles.

`recipes.csv`: plato, código de insumo y cantidad **cruda** por porción, en la unidad del
catálogo, con fuente. Es una receta técnica fija, no consumo físico medido ni receta nutricional.
Los ejemplos contienen solo algunos ingredientes: deben completarse para un estudio real.

`ingredients.csv`: código, nombre, unidad, costo por unidad en soles, presentación de compra,
vida útil supuesta en días, plazo fijo de entrega y fuente. Vida útil significa tiempo desde
recepción, bajo condiciones de conservación que deben documentarse y validarse. No es una
recomendación sanitaria. El plazo debe ser menor que el horizonte del experimento.

`context.csv` opcional: `date,expected_temperature,holiday,context_source`, una fila por día
del periodo. Temperatura esperada disponible antes de pronosticar; feriado como 0/1.
El generador añade `payday` para los días 15, 30 y 31: es un supuesto de escenario, no una
afirmación de cuándo cobran todos los trabajadores. Sin contexto, usa una curva climática
ilustrativa y los feriados nacionales de 2024–2025 documentados en El Peruano, con fuentes
en el manifiesto. Excluye los días no laborables compensables del sector público. Para otros
años no hay calendario incorporado: carga tu propio contexto. No etiqueta el clima como SENAMHI.

Los precios públicos sirven de referencia de costos, no como evidencia de ventas del
restaurante. Los volúmenes, efectos, recetas, vida útil, almacenamiento y hábitos de compra
necesitan fuentes pertinentes y revisión de expertos. Ejemplos de fuentes a consultar:

- [MIDAGRI: precios de alimentos](https://www.gob.pe/institucion/midagri/colecciones/398-precios-de-alimentos).
- [SENAMHI: descarga de datos](https://www.senamhi.gob.pe/site/descarga-datos/).

El generador no descarga ni mezcla datos oficiales automáticamente. Registra las fuentes
que efectivamente utilizaste, su fecha, unidad y cualquier transformación. Las fuentes
externas no sustituyen la validación de verosimilitud.

## Reproducción local

En PowerShell, dentro de la carpeta del proyecto:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[research]"
.venv\Scripts\python.exe -m restaurante.research.runner --templates --output data/configuracion
.venv\Scripts\python.exe -m restaurante.research.runner --generate-only --config-dir data/configuracion --seeds 42
.venv\Scripts\python.exe -m restaurante.research.runner --config-dir data/configuracion --seeds 42 --output data/research
```

Para comparar réplicas usa `--seeds 42,43,44,45,46`. Cinco es un mínimo técnico para habilitar
el cálculo inferencial en el programa, no una justificación de potencia estadística ni un
tamaño de muestra suficiente para cualquier estudio. Define el número final antes de
examinar resultados. Se guardan versiones de librerías, semilla, parámetros, huellas SHA-256,
predicciones y métricas. La reproducibilidad numérica entre hardware/versiones de TensorFlow
puede variar: conserva el entorno registrado.

Si no instalaste los extras, el programa informa qué modelos no ejecutó. Un experimento con
RF e ingenuo sirve para probar el flujo, pero no completa OE2. El modo web gratuito nunca
instala TensorFlow ni XGBoost y no modifica el plan de Render.

## Protocolo implementado

- Generación de solicitudes: media por plato, multiplicadores de contexto, ruido lognormal
  compartido por perfil, eventos aleatorios y conteo Poisson. Cerrado significa demanda cero
  explícita. Un faltante de registro no equivale a cero.
- Recetas convierten solicitudes de platos en demanda teórica por insumo-día. La disponibilidad
  no limita esa tabla. La simulación distingue demanda, atendido y no atendido.
- Partición por defecto: entrenamiento hasta 31/05/2025, validación del 01/06 al 15/09/2025,
  prueba del 16/09 al 31/12/2025. No hay mezcla aleatoria de fechas.
- Los modelos usan ventanas de los 14 días anteriores y calendario conocido. El modelo es
  conjunto para las series, con identidad de serie y escala calculada solo en entrenamiento.
  Las variantes externas añaden temperatura esperada, feriado y quincena. El calendario anual
  y semanal se mantiene en ambas variantes.
- RF compara profundidades 4/8 con 70 árboles; XGBoost 2/4 con 90 árboles y tasa .06;
  LSTM 8/16 unidades con 12 épocas por defecto. Son búsquedas pequeñas explícitas, no una
  garantía de optimización exhaustiva. La arquitectura LSTM consume secuencias reales de
  14 pasos; los árboles reciben las mismas ventanas aplanadas.
- Se seleccionan configuración y ganador por media de WAPE de validación entre series
  con demanda positiva. Si todas son cero, se usa MAE. Se reentrena con entrenamiento y
  validación; no se selecciona ganador por prueba ni por reducción de merma.
- Evaluación: bloques consecutivos de siete días, predicción recursiva dentro de cada bloque,
  sin observar su demanda. El modelo queda fijo; el historial se actualiza entre bloques.
  Para compras se emiten además pronósticos diarios, siempre con datos anteriores al origen.
- Supuesto explícito: se conocen las solicitudes anteriores incluso si no se atendieron.
  Para aplicar esto a ventas reales hay que registrar rechazos; ventas censuradas por falta
  de stock no son demanda completa. El experimento no resuelve esa falta de observación.
- MAE/RMSE/sesgo en unidades de cada insumo; MAPE excluye ceros y los cuenta; WAPE no
  se calcula si el denominador es cero; R² queda sin definir en series constantes.
  `forecast_blocks.csv` permite estudiar la variación entre bloques.
- Diebold-Mariano aproximado: pérdida cuadrática, varianza HAC Bartlett hasta horizonte−1.
  Los valores p son exploratorios por serie, sin corrección múltiple. Revisar supuestos antes
  de usarlos como contraste definitivo en el informe.

## Inventario y alcance de merma

Simulación independiente por insumo, con revisión diaria, inventario inicial idéntico,
entrega después del plazo configurado, paquetes completos y consumo PVPS. Primero vencen
lotes de fechas anteriores, se coloca pedido, se reciben entregas y se atiende la demanda.
Un lote puede usarse durante su fecha de vencimiento. No hay reposición de emergencia.

La regla empírica supuesta usa la media de demanda de las jornadas abiertas dentro de los
28 días calendario previos; respeta cierres
conocidos. La política de pronóstico usa el modelo seleccionado por validación. Ambas proyectan
consumo, vencimientos y pedidos en camino hasta la llegada y reponen la necesidad de ese día
más la misma reserva (0.2 días de demanda media previa por defecto). El inventario inicial es
un día de demanda media previa, con vida útil completa, igual en ambas políticas.

El programa mide **merma de insumos crudos por vencimiento**, no comida preparada sobrante,
merma técnica de limpieza, porciones variables, sustituciones ni desperdicio de clientes.
Un quiebre es un insumo-día con cantidad no atendida. El servicio es por insumo: no equivale
a porcentaje de platos servibles con todos sus componentes.

Merma porcentual = cantidad vencida / cantidad recibida en el periodo ×100. El inventario
inicial se informa por separado: el indicador puede verse afectado por él, especialmente en
periodos cortos. No se agregan cantidades con unidades diferentes. Para comparar réplicas se
usa costo total de vencimientos en soles y número de insumo-días con quiebre. Se informa saldo
final sin convertirlo en merma; no se encargan entregas posteriores al último día del periodo.

La reducción del 10% se interpreta **relativa**: `(empírica−pronóstico)/empírica ×100`.
Si el valor empírico es cero, la reducción porcentual queda sin definir. Varias semillas
producen comparación pareada por réplica, Wilcoxon bilateral e intervalo bootstrap del
promedio de diferencias y diferencia media estandarizada pareada cuando está definida.
`paired_replications_by_ingredient.csv` informa también **cantidad vencida por insumo**, necesaria
para contrastar la hipótesis de merma sin sustituirla por su costo. El resumen global monetario
es complementario. No se consideran los días autocorrelacionados réplicas independientes.
Los resultados siguen condicionados al generador y no prueban representatividad externa.

## Expertos y usuarios

La pantalla calcula V de Aiken por criterio con escala 1–5, verificando que todos los expertos
evalúen todos los criterios. Muestra número de expertos y no inventa intervalos de confianza.
La evaluación del informe requiere tres perfiles complementarios y criterios acordados.

SUS requiere un código anónimo por persona y `q1`…`q10`, enteros 1–5. Suma los aportes
alternados y multiplica por 2.5. Se informa puntaje 0–100, no porcentaje de satisfacción.
Usa un instrumento español validado y consentimiento; registra al menos los cinco
administradores/propietarios contemplados, tareas, ayudas y dificultades. Las plantillas
están vacías y nunca se completan con respuestas sintéticas.

## Qué falta fuera del software

Calibración con fuentes y expertos; definición validada de política empírica; congelar el
protocolo y parámetros; ejecutar réplicas definitivas; recolectar SUS y valoraciones reales;
redactar resultados tal como se obtengan. El PDF fuente no ha sido modificado. Debe ajustarse
al alcance de merma, unidad de servicio, políticas, particiones y pruebas aquí documentadas
antes de presentar resultados como cumplimiento de la tesis.
