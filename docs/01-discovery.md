# 01 · Discovery — "AndesMart" (cliente ficticio)

> Simulación de un engagement de Forward Deployed Engineer: llego sin especificaciones, entrevisto al negocio y defino qué construir.

## 1. Contexto del cliente

**AndesMart** es una cadena de tiendas de ropa con 40 tiendas en 4 países de LATAM y ~3.000 SKUs (prenda × talla × color) en categorías como polos, jeans, casacas, vestidos y calzado. Lanza 2 colecciones por año (temporada verano / invierno) más reposiciones de básicos.

- Ventas: POS de cada tienda exporta CSV diarios a un bucket.
- Inventario: el ERP genera snapshots JSON diarios por tienda/SKU.
- Compras / distribución: la reposición desde el almacén central a tiendas se decide en Excel, "a ojo", una vez por semana.
- Reportes: un analista consolida todo a mano en Excel cada lunes (≈ 1 día de trabajo).

## 2. Problema (en palabras del negocio)

> "Se nos acaban las tallas M y L de lo que más se vende y terminamos la temporada liquidando tallas XS y XL con 50% de descuento. Nos enteramos tarde, cuando el cliente ya se fue."
> — Gerente de Operaciones (simulado)

**Problema reformulado:** no hay una fuente única y confiable de ventas + inventario, y no existe ninguna anticipación de la demanda. Resultado: quiebres de stock por talla (ventas perdidas) y sobre-stock al final de temporada (rebajas que destruyen margen).

## 3. Stakeholders

| Rol | Necesidad principal | Cómo consume la solución |
|---|---|---|
| Gerente de Operaciones (sponsor) | Reducir quiebres de stock y ver el estado por tienda | Dashboard + preguntas en lenguaje natural |
| Planner de distribución / Merchandiser | Saber qué tallas/colores enviar a cada tienda cada semana | Lista de reposición sugerida |
| Gerente de tienda | Alertas de SKUs en riesgo en su tienda | Dashboard filtrado / alertas |
| Analista BI | Dejar de consolidar Excel a mano | Tablas Gold gobernadas |
| TI / Data | Seguridad, costos, mantenibilidad | Unity Catalog, CI/CD, monitoreo |

## 4. Preguntas de discovery (y supuestos tomados)

| Pregunta | Respuesta / supuesto |
|---|---|
| ¿Con qué frecuencia necesitan los datos? | Diario (D-1) es suficiente para la fase 1 |
| ¿Qué es un "quiebre de stock"? | `on_hand = 0` al cierre del día para un SKU (prenda-talla-color) que tuvo ventas en los últimos 28 días; también se mide **quiebre de curva de tallas** (falta alguna talla central del modelo) |
| ¿Horizonte de forecast útil? | 7 días (ciclo semanal de compras) |
| ¿Hay datos externos que influyan? | Clima (temperatura → casacas vs. polos), feriados y fechas comerciales (Día de la Madre, Black Friday, Navidad) |
| ¿Hay devoluciones? | Sí, ~8% de las ventas (cambio de talla); se restan de la demanda neta |
| ¿Quién puede ver qué? | Gerentes de tienda solo su país; Compras ve todo |
| ¿Calidad de datos conocida? | POS envía duplicados y algunos precios negativos |

## 5. User stories (fase 1)

| ID | Historia | Criterio de aceptación |
|---|---|---|
| US-01 | Como **analista BI**, quiero ventas e inventario consolidados diariamente en tablas confiables, para dejar de unir Excel a mano. | Tablas Gold actualizadas antes de las 07:00; 0 duplicados; reglas de calidad registradas |
| US-02 | Como **gerente de operaciones**, quiero ver la tasa de quiebre de stock por tienda y categoría, para priorizar acciones. | Dashboard con KPI de quiebre, filtros por país/tienda/categoría |
| US-03 | Como **planner**, quiero un forecast de demanda a 7 días por SKU/tienda, para pedir la cantidad correcta. | Forecast diario con error medido (WAPE) y registrado en MLflow |
| US-04 | Como **planner**, quiero una lista de SKUs (talla/color) en riesgo de quiebre en los próximos 7 días con cantidad sugerida a enviar desde el almacén. | Tabla `gold.replenishment_suggestions` con días de cobertura y cantidad sugerida |
| US-05 | Como **gerente de operaciones**, quiero preguntar en lenguaje natural ("¿qué tiendas de Chile tienen más quiebres de talla M en jeans esta semana?"). | Genie space / agente responde correctamente ≥ 8 de 10 preguntas de evaluación |
| US-06 | Como **TI**, quiero que todo se despliegue con CI/CD y con permisos gobernados. | Deploy dev/prod vía bundle + GitHub Actions; tests pasan en CI; grants en Unity Catalog |

**Fuera de alcance (fase 1):** integración real con ERP, compra de colecciones nuevas (pre-temporada), optimización de precios de rebaja, datos en tiempo real.

## 6. KPIs de éxito

| KPI | Línea base (simulada) | Meta fase 1 |
|---|---|---|
| Tasa de quiebre de stock (SKU-tienda-días) | ~4,5% global; ~12% en talla M | Visible diariamente; meta de negocio < 3% global y < 6% en tallas centrales |
| % de venta en rebaja al cierre de temporada | ~35% | Visible por categoría/talla |
| Tiempo de consolidación semanal | ~8 h manuales | 0 h (automático) |
| Error de forecast (WAPE semanal) | N/A (no hay forecast) | Superar al baseline ingenuo; < 35% a nivel tienda × modelo-color (a nivel SKU el ruido Poisson pone el piso en ~0,45) |
| Frescura de datos | Semanal | Diaria (D-1) |

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| Cuotas de Databricks Free Edition | Volumen de datos acotado (~1–2M filas), serverless, jobs cortos |
| Calidad de datos del POS | Expectations en Silver + tabla de cuarentena |
| Forecast poco preciso | Comparar siempre contra baseline naive; empezar simple |
| Alcance de la capa de IA | Genie primero (bajo esfuerzo); agente custom solo si sobra tiempo |
