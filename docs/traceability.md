# Trazabilidad del sistema y la investigación

El sistema prioriza la aclaración del usuario: disponer de software funcional para el restaurante basado en el problema investigado. La investigación completa y su validación científica requieren evidencia adicional.

| Necesidad o fuente | Funcionalidad entregada | Límite o evidencia pendiente |
|---|---|---|
| Aclaración del usuario: sistema funcional | Catálogo, recetas, recepción de compras, ventas y stock persistente | Administrador local; no facturación ni acceso multiusuario |
| PDF OE4, pp. 8–9: pronósticos y compras por insumo | Plan de consumo y compras de hasta siete días con exportación CSV | Las sugerencias requieren revisión; no crean pedidos |
| PDF marco conceptual, pp. 24–25: receta estándar | Venta descuenta cantidades por porción y conserva su consumo histórico | Cantidades de ejemplo deben ajustarse al restaurante |
| PDF, tabla de variables, pp. 10–11: merma/disponibilidad | Lotes FIFO, exclusión de vencidos, merma auditada y alertas de stock | Dashboard operativo, no comparación causal ni validación de hipótesis |
| PDF, herramientas, p. 16 | Python, Pandas, scikit-learn y Streamlit | XGBoost/LSTM no forman parte de este MVP operativo |
| PDF OE1, pp. 8 y 12–13: datos sintéticos calibrados | Demostración explícitamente separada del restaurante propio | No sustituye los tres perfiles completos, fuentes oficiales ni juicio de expertos |
| PDF OE2, pp. 8 y 15: evaluación de modelos | Random Forest operativo, referencia estacional/promedio según historial | Faltan comparación experimental, particiones de tesis, ablation, métricas y pruebas estadísticas |
| PDF OE3, pp. 8 y 15: impacto en inventario | Plan de compras simula consumo y vencimiento del stock disponible | No mide reducción de mermas ni prueba superioridad frente a política empírica |
| PDF HE4, p. 9: SUS ≥ 68 | Flujos funcionales preparados para uso local | No se han recolectado respuestas ni calculado resultados de usuarios |
| PDF integridad científica, pp. 16–17 | Etiquetas de demostración y limitaciones visibles | No se afirma que se alcanzaron umbrales de precisión o reducción de desperdicio |

Las páginas corresponden a la numeración visible del PDF de 35 páginas; su índice conserva referencias de una versión anterior. La implementación no modifica el documento fuente.

## Contratos SDD

| Capacidad | Requisitos | Verificación |
|---|---|---|
| Catálogo | CAT-1, CAT-2 | Validación de cantidades, recetas, activación e historial |
| Operación | OPS-1, OPS-2, OPS-3 | Persistencia, FIFO, vencimientos, transacciones e idempotencia |
| Planificación | PLAN-1, PLAN-2 | Historial previo al origen, fallback explícito, redondeo y asignación cronológica |
| Interfaz | UI-1, UI-2 | Elección explícita, aislamiento de espacios y compra → venta → dashboard |

Las pruebas usan bases temporales; nunca necesitan manipular los registros del restaurante propio. Los informes de verificación SDD registran lo realmente ejecutado.
