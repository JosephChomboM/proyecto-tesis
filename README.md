# Restaurante predictivo

Sistema local para administrar insumos, recetas, compras, ventas, stock y mermas, con pronósticos de consumo y sugerencias de compra. Implementa el sistema operativo que acompaña la investigación de demanda en restaurantes MYPE de Lima.

Incluye **Investigación**, un espacio separado para generar datasets sencillos, comparar
ingenuo estacional, Random Forest, XGBoost y LSTM, simular compras y calcular Aiken/SUS
con respuestas humanas. Consulta [la guía de experimentos](docs/experimentos.md) para probarlo.
Los parámetros iniciales son supuestos de ejemplo, no datos calibrados o validados de Lima.
El entrenamiento completo es local; Render gratuito permite generar datos y consultar resultados.

El plan diario reconoce feriados nacionales de 2024–2026 y permite anotar promociones,
reservas y cierres excepcionales. Muestra el contexto por fecha y compara el pronóstico
con/sin estas señales. Consulta [feriados y eventos](docs/feriados-eventos.md).

En **Configuración inicial** puedes completar tus tablas en pantalla o importar CSV de
insumos, platos, recetas, stock inicial, compras y ventas históricas, con asociación de
columnas, vista previa y guardado completo. Consulta [la guía de importación](docs/importacion-inicial.md).
El stock inicial no se registra como gasto de compra y las ventas antiguas alimentan el
pronóstico sin descontar otra vez el inventario. La web gratuita permite comenzar con una
**Prueba vacía** temporal; la persistencia local y los respaldos siguen usando SQLite.

## Iniciar

El despliegue gratuito de Render usa **demostraciones temporales separadas por sesión**:
permite explorar y registrar pruebas, pero no conserva inventario de producción.
El pipeline de GitHub Actions y la configuración están en [despliegue.md](docs/despliegue.md).

**Probar en línea:** https://mise-restaurante-tesis.onrender.com/

El servicio gratuito puede tardar un minuto o más en reactivarse después de estar inactivo.
Los cambios de `main` se publican automáticamente después de pasar las pruebas.

En Windows (PowerShell), desde la carpeta del proyecto:

```powershell
python -m pip install -e ".[dev]"
python -m streamlit run app.py
```

Con el entorno que acompaña este proyecto:

```bash
.venv/bin/python -m streamlit run app.py
```

Abre la dirección local que muestra Streamlit. Elige **Explorar demostración** para probar con datos de ejemplo o **Comenzar mi restaurante** para trabajar desde cero. Los espacios se guardan por separado y puedes cambiar entre ellos desde la barra lateral.

Para instalar desde cero con Python 3.11 o superior y `uv`:

```bash
uv venv --python 3.12
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python -m streamlit run app.py
```

## Tu primera operación

La pantalla **Resumen** reúne indicadores, alertas y accesos rápidos a compras, ventas,
inventario y planificación. **Stock y mermas** permite buscar insumos por nombre. El plan
destaca presupuesto estimado, cantidad de insumos por comprar y próxima fecha de pedido.
La interfaz adapta sus tarjetas y formularios al ancho de escritorio o móvil.

En **Reportes** elige fechas para consultar ventas, compras, mermas, porciones no atendidas
y jornadas completas. Incluye gráficos, detalle con descarga CSV y un reporte HTML que puedes
abrir en el navegador e imprimir como PDF. Los importes son registros operativos, no una utilidad.
Los reportes señalan jornadas incompletas y distinguen datos sintéticos de operaciones registradas.
En **Plan de compras** puedes filtrar las cantidades a recibir por día; su CSV respeta ese filtro.

1. En **Catálogo → Insumos**, registra nombre, unidad, costo de referencia, presentación de compra, vida útil y stock de seguridad.
2. En **Platos**, registra nombre y precio. En **Recetas**, indica cuánto insumo necesita una porción de cada plato, usando la misma unidad del inventario.
3. En **Compras**, registra lo recibido y su vencimiento. Puedes ingresar unidades de inventario (5 kg) o presentaciones (2 sacos de 50 kg). En ese caso ingresa el costo por saco: el sistema convierte cantidad y costo unitario.
4. En **Ventas**, elige el plato y sus porciones. La receta descuenta el stock automáticamente. Si falta un insumo, la venta completa se rechaza sin descontar existencias.
   También puedes abrir **Registrar el resumen del día por plato** para ingresar todas las
   porciones diarias juntas. Añade solo ventas aún no registradas; el resumen no reemplaza anteriores.
5. Consulta **Stock y mermas** para registrar pérdidas y procesar saldos vencidos. Los lotes vencidos nunca están disponibles para vender; el lote sigue vigente durante su fecha de vencimiento.
6. En **Ventas**, registra también los pedidos reales rechazados por falta de stock. No generan ingresos ni descuentos de inventario, pero completan la demanda observada.
7. En **Cierre diario**, confirma que terminaste de registrar la jornada o indica que no abriste. El cierre bloquea movimientos de esa fecha y anteriores: registra las jornadas pendientes primero, en orden.
8. En **Plan de compras**, revisa hasta siete días, los días de atención y el plazo de entrega. Descarga las sugerencias. Confirma en Compras únicamente lo que realmente recibiste.

Los formularios aceptan fechas de operación hasta hoy, según la hora de Lima. Para conservar un inventario consistente, los movimientos deben registrarse en orden cronológico. Desactivar platos o insumos conserva su historial. La unidad de un insumo con movimientos o recetas no se puede cambiar. La rotación utiliza primero lo que vence antes (PVPS), con recepción e identificador como desempate. La vida útil incluye el día de recepción: un producto de vida útil 1 vence ese mismo día, sujeto a sus condiciones reales de conservación.

Las recetas expresan peso bruto de almacén por porción; incluye la cantidad previa a limpieza o pelado. No registres nuevamente esa pérdida habitual como merma. La operación actual descuenta insumos al vender y está orientada a preparación por pedido. No modela todavía producción por lotes, sobrantes preparados ni conversiones entre crudo y cocido.

En **Stock y mermas → Corregir stock mediante conteo físico** puedes reconciliar existencias utilizables. Los faltantes quedan auditados como merma de ajuste; los excedentes crean lotes de ajuste al costo de referencia y no se suman al historial de compras. Un ajuste no anula ni corrige automáticamente una venta o compra equivocada.

## Qué significa una sugerencia

El pronóstico usa jornadas confirmadas completas: consumo de las ventas más insumos correspondientes a pedidos no atendidos, con recetas conservadas al registrar cada operación. Una jornada completa sin consumo aporta un cero conocido. Los días pendientes y días sin apertura no se convierten en consumo cero. El calendario futuro de atención se configura en el plan; deben revisarse cierres excepcionales.

Con al menos 56 días observados utiliza Random Forest; con pocos datos emplea una referencia estacional o el promedio y muestra su limitación. Los huecos del historial se excluyen como objetivos de entrenamiento; para calcular rezagos se arrastra el último dato conocido y se informa la cantidad de días faltantes. Esta imputación requiere evaluación y puede sesgar el pronóstico. Sin historial solo se puede sugerir cubrir la reserva.

El plan descuenta existencias utilizables, considera vencimientos y reserva, y redondea la compra a las presentaciones configuradas. Distribuye el stock una sola vez a lo largo de los días. Las recomendaciones posteriores suponen que recibiste las compras sugeridas antes de cada servicio. **Una sugerencia no crea una compra ni envía pedidos a proveedores.**

El plan empieza mañana. Mientras hoy esté abierto se considera preliminar, pues no descuenta ventas aún no registradas. La fecha de pedido es la fecha de recepción necesaria menos el plazo de entrega indicado. Los pedidos con fecha pasada se alertan como no garantizados. No optimiza presupuesto, capacidad de frío, mínimos por proveedor ni rutas de compra. La reserva es una cantidad fija configurable, no un intervalo de confianza.

En **Evaluación temporal del pronóstico** puedes comparar el método automático con promedio y referencia semanal. Usa tres bloques retrospectivos no superpuestos de siete días, con al menos 56 observaciones de entrenamiento por insumo. Exporta predicciones y MAE, RMSE, sesgo, WAPE y MAPE por insumo. MAPE excluye días cero e informa cuántos; WAPE es indefinido si la demanda total es cero. El resultado no constituye por sí solo una prueba causal ni una evaluación con usuarios.

## Datos y copias de seguridad

| Espacio | Archivo local |
|---|---|
| Demostración | `data/demo.sqlite3` |
| Mi restaurante | `data/restaurant.sqlite3` |

La demostración se prepara una sola vez y conserva los cambios de las siguientes sesiones. Su historial sintético está separado de las ventas operativas para no inventar movimientos de inventario. Los datos del restaurante propio nunca se rellenan con la demostración.

Para guardar los archivos en otra carpeta, define `RESTAURANTE_DATA_DIR` antes de iniciar. No compartas una misma carpeta entre varias instancias de la aplicación.

Puedes usar **Descargar respaldo completo** en la barra lateral: produce una copia SQLite consistente, incluidos datos confirmados del registro WAL. Para restaurarla, detén Streamlit y coloca la copia en una carpeta nueva con el nombre del espacio correspondiente; apunta `RESTAURANTE_DATA_DIR` a esa carpeta y conserva los originales. No mezcles una copia restaurada con archivos WAL/SHM de otra base. Los CSV no sustituyen el respaldo completo.

Las bases anteriores se amplían automáticamente al esquema 2 sin borrar registros. Sus ventas históricas se conservan, pero no se presumen jornadas completas: el historial operativo nuevo requiere cierre. Si ya existen movimientos recientes, los cierres antiguos no se reconstruyen automáticamente; requieren un proceso de migración revisado.

## Alcance y relación con la tesis

Este MVP cubre la operación de un restaurante por un administrador de confianza en un equipo local. No incluye facturación electrónica, pagos, cuentas de usuario ni publicación segura en Internet. El dashboard muestra ventas, stock y alertas; no debe interpretarse como un balance contable.

La demostración usa recetas, precios y patrones ilustrativos. No es un conjunto calibrado con fuentes oficiales ni evidencia de resultados reales. Investigación permite generar datos, comparar Random Forest/XGBoost/LSTM y una referencia estacional, y simular políticas de compra. El [estudio reproducible](docs/estudio-reproducible.md) fija cinco pilotos y treinta réplicas definitivas con tres perfiles de 2024–2025, conserva los archivos recargables y calcula comparaciones estadísticas. La calibración con datos externos, el juicio de expertos y la evaluación SUS requieren evidencia adicional. Consulta [la trazabilidad](docs/traceability.md) y [los criterios de validación](docs/validacion-peru.md).

## Desarrollo y verificación

El [estudio publicado con informe, datasets y resultados](investigacion/estudio-2026-11-26/README.md) contiene las cinco réplicas piloto y treinta definitivas, los archivos para recargarlas en Investigación y las instrucciones para repetir el entrenamiento.

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
```

Las pruebas de interfaz usan [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest) con bases temporales aisladas. Los [formularios](https://docs.streamlit.io/develop/concepts/architecture/forms) agrupan los cambios antes de enviarlos. Las especificaciones, decisiones y tareas SDD están en `openspec/changes/restaurant-demand-system/`.
