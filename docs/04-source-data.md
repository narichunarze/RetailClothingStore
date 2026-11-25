# 04 · Datos fuente

Generados con `src/data_gen/generate.py`, una simulación día a día de demanda, inventario, reposición y devoluciones. Los datos llegan "tal cual" los envían los sistemas fuente, con problemas de calidad incluidos a propósito para resolverlos en Silver.

## Cómo generarlos

```bash
# 1) (opcional) clima y feriados reales: necesita internet
python -m src.data_gen.ingest_external --out data/raw --start 2025-01-01 --end 2025-12-31

# 2) simulación de 1 año (~5 s, ~90 MB)
python -m src.data_gen.generate --out data/raw --truth data/truth \
  --weather-dir data/raw/weather --holidays-dir data/raw/holidays

# 3) subir al volume de Unity Catalog
databricks fs cp -r data/raw dbfs:/Volumes/workspace/andesmart_dev/raw
```

Sin `--weather-dir` y `--holidays-dir` se usa una temperatura sintética y no se aplica el efecto de feriados.

## Fuentes

| Ruta | Sistema simulado | Formato | Grano |
|---|---|---|---|
| `master/products.csv` | PIM | CSV | SKU (modelo × color × talla) |
| `master/stores.csv` | ERP | CSV | tienda |
| `sales/date=*/sales.csv` | POS | CSV diario | línea de ticket |
| `returns/date=*/returns.csv` | POS | CSV diario | devolución |
| `inventory/date=*/inventory.jsonl.gz` | ERP | JSON lines gzip | tienda × SKU × día (cierre) |
| `weather/city=*/weather.json` | Open-Meteo | JSON | ciudad × día |
| `holidays/country=*/<año>.json` | Nager.Date | JSON | feriado |
| `../truth/lost_sales.csv.gz` | — (verdad de terreno) | CSV gzip | demanda no atendida. **No se ingesta**; sirve para validar la solución |

## Volumen (defaults: 12 tiendas, 40 modelos, 365 días)

~760 SKUs · ~6.800 pares tienda-SKU · ~620k líneas de venta · ~54k devoluciones · ~2,4M filas de inventario.

## Comportamientos de negocio simulados

- **Temporadas por hemisferio:** en enero se venden polos en Lima y casacas en CDMX; Colombia (ecuatorial) es estable.
- **Clima:** más calor sube la venta de polos y shorts; más frío, la de casacas y chompas.
- **Fechas comerciales:** Día de la Madre (2.º domingo de mayo; 10 de mayo en México), Black Friday hasta Cyber Monday con 20% de descuento, y la campaña navideña.
- **Liquidación de fin de temporada:** 30% y luego 50% de descuento, que sube la demanda.
- **Cerrado** el 1 de enero y el 25 de diciembre.
- **Devoluciones:** ~8% de las ventas (×1,5 en vestidos y calzado), con 1 a 14 días de rezago. Vuelven a stock salvo las de motivo "defecto".
- **Causa raíz de los quiebres:** el planner repone cada lunes (llega el jueves) mirando la venta del **modelo-color**, y reparte el pedido **en partes iguales entre tallas**. Por eso las tallas M y L (y 38 a 40 en calzado) se quiebran, y XS/XXL se acumulan.

Resultado con los defaults: quiebre global ~4,5% de tienda-SKU-días (M ~12%, L ~9%, XS ~0,3%), y ~5,5% de la demanda no atendida.

## Problemas de calidad inyectados

| Problema | Tasa | Regla Silver esperada |
|---|---|---|
| Línea POS re-enviada en el archivo del día siguiente | 0,5% | dedupe por `transaction_id` |
| Precio unitario negativo | 0,1% | `expect_or_drop unit_price >= 0` → cuarentena |
| `store_id` nulo | 0,2% | `expect_or_drop store_id IS NOT NULL` |
| SKU en minúsculas | 0,3% | `upper(sku)` |
| Tienda sin snapshot de inventario ese día | 1% de tienda-días | detectar huecos / forward-fill |
| `on_hand` negativo | 0,05% | `expect on_hand >= 0` (warn) |
