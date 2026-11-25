# 09 · Backtest de la política de reposición

**Pregunta del negocio:** *"Si reponemos como propone la solución, ¿cuánto bajan los quiebres y cuánto inventario extra necesitamos?"*

Como el negocio es simulado, se puede hacer un **contrafactual exacto**: el mismo año con la misma demanda (las mismas semillas aleatorias), cambiando solo cómo repone el planner cada lunes.

| Política | Qué hace |
|---|---|
| `even_split` (hoy) | Venta reciente del modelo-color, repartida **en partes iguales** entre tallas |
| `size_curve` | El mismo total, repartido según la **curva de tallas observada** |
| `size_aware` (solución) | Total con **demanda sin censura** (venta + venta perdida) y curva observada. Es lo que hacen el forecast y la venta perdida estimada |

```bash
python -m src.data_gen.backtest_policy --seeds 42 7 123
```

## Resultados (promedio de 3 semillas, 1 año, 12 tiendas)

| Política | Quiebre | Fill rate | Venta perdida (u.) | vs. hoy | Inventario vs. hoy | Quiebre M | Quiebre XS |
|---|---|---|---|---|---|---|---|
| `even_split` (hoy) | 5,5% | 95,0% | 37.247 | — | — | 12,9% | 0,4% |
| `size_curve` | 3,8% | 97,7% | 17.502 | **−53%** | −2,6% | 3,7% | 3,8% |
| `size_aware` | **3,5%** | **97,8%** | **16.135** | **−57%** | +0,4% | 3,3% | 3,5% |

## Lectura

- **Corregir solo la curva de tallas ya recupera más de la mitad de la venta perdida, con *menos* inventario.** Es la palanca principal y no requiere comprar más.
- Usar demanda sin censura suma otro ~4 puntos de reducción.
- El quiebre se **iguala entre tallas**: M baja de 12,9% a 3,3%, y XS sube de 0,4% a 3,5% porque deja de sobrar stock en tallas que casi no se venden. Es el trade-off esperado.
- Aquí "quiebre" = SKU con demanda en los últimos 14 días que cierra sin stock. La definición es parecida a la de Gold (28 días de venta), pero no idéntica.

## Limitaciones

- La demanda es simulada, así que el resultado dice que la política funciona **si la demanda se comporta como el modelo de negocio asumido**. Con un cliente real, el siguiente paso sería un piloto A/B: unas tiendas con la política nueva y otras como control, durante 4 a 6 semanas.
- `size_aware` usa la demanda real del simulador como proxy de "venta + venta perdida estimada". En la solución real esa estimación tiene ~8% de error.
