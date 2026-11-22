# Feriados y eventos en el plan diario

En **Plan de compras → Feriados y eventos especiales** puedes consultar el calendario
peruano y registrar promociones, reservas grandes, cierres excepcionales o una fecha
declarada como feriado local. El administrador no necesita marcar los feriados nacionales
al ingresar cada venta: se obtienen automáticamente de la fecha.

El calendario incorporado cubre 2024, 2025 y 2026. Las fuentes históricas 2024–2025 se
comparten con Investigación; para 2026 se usa [el calendario publicado en El Peruano](https://elperuano.pe/noticia/286039-fin-de-semana-largo-el-2-de-enero-del-2026-sera-dia-no-laborable).
Comprende 16 feriados nacionales por año, incluidos Jueves y Viernes Santo en sus fechas
correspondientes. Excluye los días no laborables compensables del sector público y no
supone que el restaurante cierre en un feriado. Las fechas fuera de la cobertura se
señalan **por verificar**: no se proyectan leyes a otros años ni se consultan APIs pagadas.

## Qué considera el pronóstico

Random Forest recibe el historial reciente, los ciclos del calendario y los indicadores
de feriado, cobertura de calendario, promoción, reserva y otro evento. Se ajusta con los
registros anteriores al origen; no multiplica la demanda por un porcentaje prefijado.
La etiqueta de feriado permite aprender un efecto genérico, no garantiza conocer el
efecto específico de cada celebración. Promociones y reservas se distinguen por tipo,
no por el texto de su descripción.

Si no hay suficientes jornadas para entrenar Random Forest, se mantiene la referencia
semanal o el promedio; esas referencias **no ajustan por feriados o promociones**. La
interfaz informa contexto incluido y cantidad de antecedentes en el detalle de pronóstico,
y advierte si hay menos de tres antecedentes o no hay modelo. Tres antecedentes es una
regla de aviso, no una certificación de precisión ni un tamaño de muestra validado.

Un cierre excepcional fija demanda y reserva de compra de ese día en cero, incluso con
poco historial. Una reserva grande es una señal de contexto: no añade automáticamente
porciones, pedidos ni ventas, pues todavía no existe un registro de reservas cuantificadas
por plato. Revisa manualmente la recomendación si esa reserva no tiene antecedentes.

## Registro y trazabilidad

Hay un evento especial por fecha; guardar esa fecha de nuevo añade una revisión y la
última versión queda vigente. **Retirar evento** agrega otra revisión: no elimina el
historial ni modifica el calendario nacional. El evento se guarda en la base de datos
de su espacio de trabajo y está incluido en el respaldo SQLite. La demostración pública
mantiene su carácter temporal y su aislamiento entre sesiones.

Cada revisión conserva su fecha real de registro y su hora UTC. Puedes anotar un evento
histórico para que el modelo de hoy lo conozca. Las evaluaciones de fechas anteriores a
ese registro no lo usarán: solo reconstruyen las revisiones disponibles al cierre del día
anterior a cada origen. No se afirma que una anotación retrospectiva era conocida antes
de su registro. El historial operativo de ventas y cierres no se reescribe.

## Cómo comprobar si ayuda

En **Evaluación temporal del pronóstico**, el sistema compara automático **con contexto**,
automático **sin contexto**, promedio y referencia semanal, usando los mismos orígenes y
pares observados. Los dos modelos automáticos reciben los mismos cierres conocidos; solo
varía la inclusión de indicadores como características de aprendizaje. Así se puede medir
si el contexto realmente ayuda, sin afirmar que todos los restaurantes venden más en feriados.

La tabla de próximos días y el CSV de compras muestran el contexto de cada fecha; el CSV
de pronósticos conserva las banderas, el método, si el modelo incorporó el contexto y sus
antecedentes. Esto conecta los feriados con la operación diaria, además del experimento
separado de la tesis. El clima continúa en Investigación: no se añadió una conexión de
pronóstico meteorológico ni se integró automáticamente su modelo ganador al plan diario.
