# AI Log — desarrollo AI-first con criterio

Registro de cómo se usó IA (Claude Code, Cursor, etc.) y, sobre todo, **qué se validó o corrigió**. Esto evidencia el requisito: *"Evaluate, validate, and refine AI-generated code… rather than relying blindly on AI-generated outputs."*

| Fecha | Herramienta | Tarea | Qué generó la IA | Qué revisé / corregí y por qué | Resultado |
|---|---|---|---|---|---|
| 2026-11-25 | Claude Code | Planeamiento | Borrador de discovery, arquitectura, ADRs y estructura del repo | Ajustar supuestos de negocio y alcance a cuotas de Free Edition | Docs en `docs/` |
| 2026-11-25 | Claude Code | Generador de datos sintéticos (Fase 1) | Simulación vectorizada con numpy: demanda, inventario, reposición, devoluciones | 1.ª versión: la demanda perdida era 3× lo vendido (espiral: el planner repone según venta ya censurada por quiebres). Cambié la reposición a nivel modelo-color con cobertura de 21 días y stock mínimo de exhibición. Validé con diagnóstico: quiebre ~4,5%, concentrado en M/L | `src/data_gen/`, 7 tests |
| 2026-11-25 | Claude Code | Bronze + Silver (Fase 2) | Pipelines Lakeflow con `pyspark.pipelines`, reglas de calidad y cuarentena; lógica en `src/transforms.py` | Bronze sin inferir tipos para no perder datos. Evité choque entre la columna `city` del JSON y la carpeta `city=` con `recursiveFileLookup`. Tests de duplicados fallaban: con ~54 ventas/día el 0,5% redondea a 0 → subí las tasas solo en el fixture de tests | 15 tests en verde |
| | | | | | |

## Patrones aprendidos
- _Ej.: la IA tiende a usar `collect()` en transformaciones; lo reemplazo por operaciones distribuidas._
