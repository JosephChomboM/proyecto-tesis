# Resultados del estudio computacional

Estudio ejecutado el 26 de noviembre de 2026 y publicado en el repositorio el 27 de noviembre. Incluye cinco réplicas piloto y treinta definitivas, con menú criollo, cevichería y pollería en 2024–2025. Cada réplica contiene tres perfiles, nueve platos y 24 series de insumos.

## Descargas

- [Informe editable con resultados y discusión](informe_resultados.docx).
- [Paquete completo reproducible](paquete_reproducible.zip): código utilizado, datasets, resultados, informe y guía.
- [Los 35 datasets](todos_los_datasets.zip).
- [Guía para repetir las pruebas](LEEME.txt) y [diccionario de datos](DICCIONARIO_DATOS.txt).

Para una prueba sencilla, descarga [dataset-2001.zip](final/dataset-2001.zip) y [results-2001.zip](final/results-2001.zip). La semilla 2001 se eligió por ser la primera definitiva, sin seleccionar por desempeño.

En [la aplicación](https://mise-restaurante-tesis.onrender.com/), entra en **Investigación**. En **1 · Dataset**, abre **Volver a cargar un dataset de investigación**, carga el ZIP individual y pulsa **Abrir dataset guardado**. En **2 · Experimento**, carga el ZIP de resultados y pulsa **Abrir resultados del experimento**; consúltalo en **3 · Resultados**. Los ZIP individuales se suben sin descomprimir. El paquete general primero debe descomprimirse.

## Resultados consolidados

| Indicador | Resultado de las treinta réplicas definitivas |
|---|---|
| Modelo seleccionado en validación | XGBoost; con contexto en 23 réplicas y sin contexto en 7 |
| MAPE medio del modelo seleccionado | 22,70 %; no alcanza la meta media inferior al 20 % |
| WAPE medio del modelo seleccionado | 20,20 % |
| Reducción de insumo días con quiebre | 20,87 % |
| Reducción de cantidad vencida total | 2,13 %; diferencia no concluyente, p exploratoria = 0,0732 |
| Variación del costo de vencimiento | Aumento de 1,45 % |

El informe detalla las diferencias por insumo, intervalos bootstrap y contrastes pareados con ajuste Holm. Los pilotos están excluidos de las estadísticas definitivas. Las réplicas son semillas de una simulación; no son una muestra de restaurantes reales.

**Alcance:** datos sintéticos con supuestos no calibrados. Costos, recetas parciales, plazos, vidas útiles y política empírica no están validados con restaurantes. La validación por expertos y el SUS requieren participantes reales y siguen pendientes. Los resultados corresponden a Investigación y su simulador; el Plan de compras operativo conserva su propio selector.

## Archivos para auditoría

- `configuracion/`: perfiles, recetas e ingredientes.
- `pilot/`: cinco datasets, sus resultados y comprobantes de integridad.
- `final/`: treinta datasets, sus resultados y comprobantes de integridad.
- `resumen/`: métricas y análisis consolidados en CSV.
- `figuras/`: gráficos usados en el informe.
- `protocolo_congelado.json`, `versiones.json` y `registro_ejecucion.json`: reglas, entorno y verificaciones realizadas.
- `requirements-estudio.txt`: dependencias fijadas para repetir el entrenamiento.
- `SHA256SUMS.txt`: huellas de los archivos **dentro de paquete_reproducible.zip**, con las rutas internas de ese paquete.

Para entrenar de nuevo, usa el código del paquete y una carpeta de salida nueva, siguiendo `LEEME.txt`. No alteres los datos publicados para buscar resultados favorables. Los modelos pueden presentar pequeñas diferencias numéricas entre equipos.

Los datos operativos SQLite, credenciales, entornos virtuales y archivos temporales no forman parte de esta entrega.
