# Trazabilidad del sistema y la investigación

El sistema combina operación diaria con un espacio de experimentación separado. El protocolo
implementado se detalla en [experimentos.md](experimentos.md). La calibración y la validación
científica con expertos y usuarios requieren evidencia que no puede generar el software.

| Necesidad o fuente | Funcionalidad entregada | Límite o evidencia pendiente |
|---|---|---|
| Aclaración del usuario: sistema funcional | Catálogo, recetas, recepción de compras, ventas y stock persistente | Administrador local; no facturación ni acceso multiusuario |
| PDF OE4, pp. 8–9: pronósticos y compras por insumo | Plan de consumo y compras de hasta siete días con exportación CSV | Las sugerencias requieren revisión; no crean pedidos |
| PDF marco conceptual, pp. 24–25: receta estándar | Venta descuenta cantidades por porción y conserva su consumo histórico | Cantidades de ejemplo deben ajustarse al restaurante |
| PDF, tabla de variables, pp. 10–11: merma/disponibilidad | Lotes PVPS, exclusión de vencidos, merma auditada y alertas de stock | Dashboard operativo, no comparación causal ni validación de hipótesis |
| PDF, herramientas, p. 16 | Operación ligera; extra local research para XGBoost/TensorFlow | El servidor gratuito no entrena redes |
| PDF OE1, pp. 8 y 12–13: datos sintéticos calibrados | Generador 2024–2025, tres perfiles editables, recetas, fuentes/supuestos y semillas; feriados documentados | Clima y volúmenes de ejemplo; faltan calibración y juicio de expertos |
| PDF OE2, pp. 8 y 15: evaluación de modelos | Ingenuo, RF, XGBoost y LSTM; búsqueda temporal, variantes externas, prueba reservada, métricas y DM aproximado | Ejecutar protocolo definitivo y revisar supuestos inferenciales; los ejemplos no confirman hipótesis |
| PDF OE3, pp. 8 y 15: impacto en inventario | Políticas pareadas, entregas, vencimientos, paquetes, saldo final y réplicas con Wilcoxon/bootstrap | Política empírica pendiente de validación; merma solo por vencimiento de insumos crudos |
| PDF HE4, p. 9: SUS ≥ 68 | Tareas de prueba, importación de respuestas reales y cálculo SUS/Aiken | No se han recolectado respuestas de usuarios ni expertos |
| PDF integridad científica, pp. 16–17 | Etiquetas de demostración y limitaciones visibles | No se afirma que se alcanzaron umbrales de precisión o reducción de desperdicio |

Las páginas corresponden a la numeración visible del PDF de 35 páginas; su índice conserva referencias de una versión anterior. La implementación no modifica el documento fuente.

## Contratos SDD

| Capacidad | Requisitos | Verificación |
|---|---|---|
| Catálogo | CAT-1, CAT-2 | Validación de cantidades, recetas, activación e historial |
| Operación | OPS-1, OPS-2, OPS-3 | Persistencia, PVPS, vencimientos, transacciones e idempotencia |
| Planificación | PLAN-1, PLAN-2 | Historial previo al origen, fallback explícito, redondeo y asignación cronológica |
| Interfaz | UI-1, UI-2 | Elección explícita, aislamiento de espacios y compra → venta → dashboard |

Las pruebas usan bases temporales; nunca necesitan manipular los registros del restaurante propio. Los informes de verificación SDD registran lo realmente ejecutado.

## Ampliación operativa e investigación

La revisión implementa cierre diario, ceros explícitos, pedidos no atendidos, ajustes auditados, respaldo consistente, compras por presentación y evaluación temporal de tres estrategias. El registro científico de pendientes y el protocolo de usuarios están en [validacion-peru.md](validacion-peru.md). La evaluación automática no sustituye juicio de expertos, SUS ni pruebas de impacto en inventario.
