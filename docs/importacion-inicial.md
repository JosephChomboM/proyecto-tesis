# Configuración inicial e importación de CSV

La aplicación guarda los datos en **SQLite**, por espacio de trabajo. El uso local conserva
la base en disco. Render Free continúa siendo una demostración con bases temporales por
sesión: descarga el respaldo antes de salir. Esta ampliación no activa discos ni servicios pagados.

## Empezar sin archivos

Entra a **Configuración inicial → Completar en pantalla**. Al iniciar un restaurante propio
se abre este menú automáticamente. En la web pública puedes elegir **Configurar restaurante
de prueba** para comenzar vacío, sin mezclar la información con los ejemplos.

1. **Insumos:** nombre, unidad, costo por unidad, presentación, vida útil y reserva.
2. **Platos:** nombre y precio por porción.
3. **Recetas:** una fila por insumo de cada plato, con cantidad cruda por porción y unidad.
4. **Stock inicial:** lotes que realmente tienes al comenzar, con cantidad, costo y vencimiento.
5. **Ventas históricas**, opcional: resumen completo de platos vendidos por fecha.

Completa la tabla como una hoja de cálculo. Pulsa **Revisar tabla inicial** y después
**Guardar tabla inicial**. Hasta el segundo botón, los datos reales no cambian. No necesitas
escribir código, conocer identificadores ni completar todos los pasos de una sola vez.
Si empiezas sin existencias, omite el stock inicial y registra tus compras cuando lleguen.

## Aprovechar un CSV existente

Abre **Importar CSV** y elige qué contiene el archivo. Descarga la plantilla del paso si la
necesitas; su fila es ilustrativa y debes reemplazarla. No es obligatorio subir todos los CSV.

| Tipo | Columnas de la plantilla |
|---|---|
| Insumos | insumo, unidad, costo_unitario, presentacion, vida_util_dias, stock_seguridad |
| Platos | plato, precio |
| Recetas | plato, insumo, cantidad, unidad |
| Stock inicial | insumo, cantidad, unidad, costo_unitario, fecha, vencimiento |
| Compras recibidas | referencia, insumo, cantidad, unidad, costo_unitario, fecha, vencimiento |
| Ventas históricas | fecha, plato, porciones; no_atendidas opcional |

Puedes conservar tus encabezados y asociar cada columna con su campo. El sistema sugiere
equivalencias como `Nombre`, `Producto`, `Cantidad`, `Vendidos`, `Fecha venta` o `unit_cost`.
Los encabezados que no se asocian se ignoran. Las plantillas de **Investigación** son distintas:
no se utilizan para cargar el restaurante operativo.

Se aceptan CSV UTF-8 y Windows-1252, separados por coma, punto y coma o tabulación.
Selecciona explícitamente decimal con punto/coma y fechas `AAAA-MM-DD` o `DD/MM/AAAA`.
No uses separadores de miles. No hay conversión implícita de unidades: 250 g deben convertirse
a 0.250 kg si ese insumo está configurado en kg. Máximo: 5 MB y 10000 filas por archivo.

Pulsa **Validar y previsualizar**. El sistema prueba la importación completa en una copia
temporal de la base. Si hay errores, informa la fila o el conflicto. Después pulsa
**Confirmar importación**: el archivo se guarda en una sola transacción y se valida de nuevo
contra el estado actual. Si una fila falla, no se conserva ninguna modificación del archivo.

## Reglas para no alterar los registros existentes

- Insumos y platos se identifican por nombre, sin distinguir mayúsculas. Datos iguales no
  se duplican. Si el nombre existe con otros datos o está inactivo, se rechaza la carga;
  edita conscientemente en **Catálogo**.
- Las recetas se cargan completas por plato. Una receta ya existente no se reemplaza
  silenciosamente ni se completa por partes mediante archivos sucesivos. Edítala en Catálogo.
- El stock inicial usa una única **fecha de conteo**, se registra antes de los movimientos
  y se distingue de una compra. Tiene lotes y costo para inventario, pero no suma gastos de
  compras del periodo. Solo se carga una vez; los cambios posteriores usan el conteo de
  **Stock y mermas**. Su costo y vida útil deben corresponder al producto y conservación reales.
- Las compras recibidas mantienen el orden cronológico, las jornadas cerradas y los
  vencimientos. Cada línea tiene una referencia única, por ejemplo `BOLETA-123-LINEA-1`.
  La misma referencia con datos iguales se omite; con datos diferentes se rechaza.
- Repetir el mismo contenido, incluso con otro nombre de archivo, no vuelve a guardarlo.
  No se admiten filas o claves duplicadas dentro del archivo. Para lotes realmente iguales
  de stock inicial, consolida su cantidad en una fila.

## Ventas antiguas y pronóstico

Las ventas históricas se guardan por separado de las ventas operativas. No generan nuevos
ingresos ni descuentan el stock disponible hoy. Puedes cargarlas después del stock inicial,
siempre que sus fechas sean anteriores al primer movimiento operativo o conteo inicial y
anteriores a hoy. No se superponen con jornadas históricas ya importadas. Si tienes varios
archivos, cada fecha completa debe aparecer en un único archivo.

Confirma que todas las jornadas incluidas están completas y revisaste las recetas. Cada
fecha incluida se interpreta como un resumen completo: los platos configurados no incluidos
se consideran sin ventas ese día. Para declarar una jornada abierta con cero ventas, incluye
una fila de un plato con cero porciones. Las fechas ausentes no se convierten en ceros.

El sistema estima los insumos con las recetas actuales y conserva ese resultado: editar
una receta posteriormente no reescribe los datos históricos importados. Esta aproximación
requiere comprobar que las recetas representen ese periodo. Si hubo cambios de menú o de
porciones no documentados, la estimación puede ser incorrecta.

Si conoces solicitudes rechazadas, asocia `no_atendidas`; si la columna no existe se interpreta
que no se registraron rechazos, no que nunca existieron. El historial será una estimación
basada en ventas conocidas y no necesariamente toda la demanda potencial. El plan utiliza
esas jornadas y las etiqueta `imported_sales_complete`. Se conserva una fila insumo-día para
los insumos activos al importar, incluidos ceros explícitos. Los movimientos operativos
posteriores no pueden retroceder a las fechas ya importadas.

En **Revisar lo guardado** puedes ver y descargar catálogos, recetas, lotes, ventas históricas
y el registro de importaciones. **Reportes → Detalle y descargas → Ventas históricas importadas**
las muestra por separado, sin sumarlas a los ingresos operativos. El respaldo SQLite incluye
el historial, sus cantidades calculadas, lotes iniciales y registro de importaciones.
