# Validación operativa e investigación

## Alcance implementado

Prototipo local para un administrador. Gestión de inventario por lotes, recetas en peso bruto,
compras por unidad o presentación, venta por pedido, PVPS, mermas, ajustes por conteo,
registro de pedidos no atendidos, cierre de jornadas y planificación de recepciones con fechas
de pedido. Pronóstico Random Forest y referencias básicas, evaluación temporal exportable.

La vida útil no certifica inocuidad. Debe definirse según producto, conservación, apertura y
procedimientos del negocio. El software no controla temperaturas ni cadena de frío.

## Referencias para contextualizar y calibrar

- MINSA/DIGESA, NTS 142, norma sanitaria de restaurantes: identificación de ingreso y vencimiento,
  rotación PEPS o PVPS. La elección del prototipo es PVPS para priorizar perecibles.
  https://www.digesa.minsa.gob.pe/normaslegales/normas/rm_822-2018-minsa.pdf
- MIDAGRI, precios referenciales por mercado y presentación. Debe distinguirse precio mayorista,
  minorista, pollo vivo y producto limpio; no son equivalentes.
  https://www.gob.pe/554-herramientas-para-consultar-precios-de-alimentos-mi-caserita
  https://www.gob.pe/institucion/midagri/informes-publicaciones/1211-boletin-de-precios-diarios-de-alimentos

Estas referencias orientan el diseño. No se han cargado precios oficiales ni calibrado las
porciones de demostración. Para hacerlo, conservar fuente, fecha, mercado, unidad y transformación.

## Supuestos que deben medirse

1. Registrar ventas completas y pedidos rechazados requiere disciplina. La demanda sigue siendo
   parcialmente observada: no incorpora clientes que se retiraron sin formular un pedido.
2. El cierre congela la información del día y evita entrenar con servicios incompletos. No abrir
   se diferencia de abrir y vender cero. Las fechas omitidas permanecen desconocidas.
3. Los huecos se imputan por arrastre únicamente para rezagos; sus objetivos no se entrenan.
   Documentar porcentaje de datos faltantes y hacer análisis de sensibilidad.
4. La reserva fija y el plazo de entrega son supuestos explícitos del usuario. El plan muestra
   recepción necesaria y fecha de pedido, pero no garantiza disponibilidad del proveedor.
5. Ajustes por conteo no equivalen necesariamente a deterioro: separar su motivo de las mermas
   físicas al analizar indicadores de la tesis.
6. Las recetas descuentan al vender. Producción por lotes y sobrantes preparados siguen pendientes;
   esta limitación debe resolverse o excluirse del alcance experimental de menús y pollerías.

## Evidencia computacional disponible

- Pruebas de persistencia, transacciones, idempotencia, vencimientos y PVPS.
- Pruebas de cierre, ceros conocidos, demanda no atendida sin ingresos ni consumo y snapshots.
- Reconciliación por conteo y distinción entre lote de ajuste y compra real.
- Respaldo SQLite consistente y reapertura independiente.
- Evaluación de origen móvil: tres bloques de siete días, entrenamiento solo anterior al origen,
  mismo conjunto de pares reales para las estrategias automática, promedio y semanal.
- Métricas por insumo: MAE, RMSE, sesgo, WAPE; MAPE excluye ceros explícitamente.

La evaluación mide cada origen sin actualizarlo con observaciones del propio bloque de prueba.
No realiza ajuste de hiperparámetros ni demuestra superioridad estadística. Los resultados de
demostración son sintéticos. No agregar MAE en kg y litros en un único indicador.

## Pendiente para contrastar la tesis

| Componente | Evidencia que falta |
|---|---|
| Datos 2024–2025 y tres perfiles | Generador calibrado, manifiesto de fuentes, parámetros, semillas y juicio de expertos |
| Comparación de algoritmos | XGBoost/LSTM, ajuste temporal, conjunto final de prueba reservado y variables externas disponibles al predecir |
| Impacto de compras | Simulación de políticas con idéntica demanda, inventario inicial, caducidad, entrega y precios; repeticiones con distintas semillas |
| Inferencia estadística | Efectos e intervalos, dependencia temporal y corrección por comparaciones múltiples |
| Uso real | Participantes, consentimiento, tareas cronometradas, errores, entrevistas y SUS |
| Operación de cocina | Preparación por lotes, rendimientos, sobrantes y anulaciones auditadas |

## Protocolo de prueba con administradores

Usar una base de prueba, sin datos reales. Pedir sin explicar los pasos:

1. Registrar arroz en kg, presentación de 50 kg, y un plato con 0.2 kg por porción.
2. Recibir dos sacos a S/ 180 cada uno: verificar 100 kg y costo S/ 3.60/kg.
3. Registrar una venta y revisar el descuento de stock.
4. Registrar un pedido no atendido: comprobar que no cambia ingresos ni stock.
5. Registrar un faltante mediante conteo físico y explicar el motivo.
6. Cerrar la jornada; interpretar la diferencia entre día cerrado y día sin apertura.
7. Interpretar demanda, reserva, recepción y fecha de pedido en el plan.
8. Descargar un respaldo y explicar dónde quedan guardados los registros.

Medir éxito sin ayuda, tiempo por tarea, errores, solicitudes de ayuda y comentarios. Aplicar
SUS al terminar y conservar las respuestas originales. No asignar un puntaje SUS por inspección
del código ni presentar estas pruebas automáticas como evaluación de usuarios.
