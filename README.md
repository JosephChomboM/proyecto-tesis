# Restaurante predictivo

Sistema local para administrar insumos, recetas, compras, ventas, stock y mermas, con pronósticos de consumo y sugerencias de compra. Implementa el sistema operativo que acompaña la investigación de demanda en restaurantes MYPE de Lima.

## Iniciar

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

1. En **Catálogo → Insumos**, registra nombre, unidad, costo de referencia, presentación de compra, vida útil y stock de seguridad.
2. En **Platos**, registra nombre y precio. En **Recetas**, indica cuánto insumo necesita una porción de cada plato, usando la misma unidad del inventario.
3. En **Compras**, registra lo recibido y su vencimiento. La cantidad se ingresa en unidades de inventario; por ejemplo, 5 kg de arroz.
4. En **Ventas**, elige el plato y sus porciones. La receta descuenta el stock automáticamente. Si falta un insumo, la venta completa se rechaza sin descontar existencias.
5. Consulta **Stock y mermas** para registrar pérdidas y procesar saldos vencidos. Los lotes vencidos nunca están disponibles para vender; el lote sigue vigente durante su fecha de vencimiento.
6. En **Plan de compras**, revisa hasta siete días y descarga las sugerencias. Confirma en Compras únicamente lo que realmente recibiste.

Los formularios aceptan fechas de operación hasta hoy, según la hora de Lima. Para conservar un inventario consistente, los movimientos deben registrarse en orden cronológico. Desactivar platos o insumos conserva su historial. La unidad de un insumo con movimientos no se puede cambiar.

## Qué significa una sugerencia

El pronóstico estima consumo por insumo a partir de ventas registradas. Con suficiente historial utiliza Random Forest; con pocos datos emplea una referencia estacional o el promedio y muestra su limitación. Sin historial no inventa consumo: solo puede sugerir cubrir el stock de seguridad.

El plan descuenta existencias utilizables, considera vencimientos y reserva, y redondea la compra a las presentaciones configuradas. Distribuye el stock una sola vez a lo largo de los días. Las recomendaciones posteriores suponen que recibiste las compras sugeridas antes de cada servicio. **Una sugerencia no crea una compra ni envía pedidos a proveedores.**

La aplicación no informa una precisión que no haya sido medida. Las ventas perdidas por falta de stock no quedan representadas como demanda observada; registra las ventas con constancia para construir un historial útil.

## Datos y copias de seguridad

| Espacio | Archivo local |
|---|---|
| Demostración | `data/demo.sqlite3` |
| Mi restaurante | `data/restaurant.sqlite3` |

La demostración se prepara una sola vez y conserva los cambios de las siguientes sesiones. Su historial sintético está separado de las ventas operativas para no inventar movimientos de inventario. Los datos del restaurante propio nunca se rellenan con la demostración.

Para guardar los archivos en otra carpeta, define `RESTAURANTE_DATA_DIR` antes de iniciar. No compartas una misma carpeta entre varias instancias de la aplicación.

Antes de mover el sistema o actualizarlo, detén Streamlit y copia la carpeta de datos completa a un respaldo seguro. Conserva los archivos originales hasta comprobar que la copia abre correctamente. Los CSV son útiles para consultar registros; no sustituyen la copia completa de la base de datos. La aplicación no incluye funciones que borren o reinicien automáticamente tus registros.

## Alcance y relación con la tesis

Este MVP cubre la operación de un restaurante por un administrador de confianza en un equipo local. No incluye facturación electrónica, pagos, cuentas de usuario ni publicación segura en Internet. El dashboard muestra ventas, stock y alertas; no debe interpretarse como un balance contable.

La demostración usa recetas, precios y patrones ilustrativos. No es un conjunto calibrado con fuentes oficiales ni evidencia de resultados reales. Quedan como trabajo de investigación: calibración con fuentes verificables, tres perfiles completos de 2024–2025, comparación controlada Random Forest/XGBoost/LSTM, métricas y pruebas estadísticas, simulación comparativa de políticas, juicio de expertos y evaluación SUS. Consulta [la trazabilidad](docs/traceability.md).

## Desarrollo y verificación

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
```

Las pruebas de interfaz usan [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest) con bases temporales aisladas. Los [formularios](https://docs.streamlit.io/develop/concepts/architecture/forms) agrupan los cambios antes de enviarlos. Las especificaciones, decisiones y tareas SDD están en `openspec/changes/restaurant-demand-system/`.
