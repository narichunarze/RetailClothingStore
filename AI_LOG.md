# AI Log — desarrollo AI-first con criterio

Registro de cómo se usó IA (Claude Code, Cursor, etc.) y, sobre todo, **qué se validó o corrigió**. Esto evidencia el requisito: *"Evaluate, validate, and refine AI-generated code… rather than relying blindly on AI-generated outputs."*

| Fecha | Herramienta | Tarea | Qué generó la IA | Qué revisé / corregí y por qué | Resultado |
|---|---|---|---|---|---|
| 2026-11-25 | Claude Code | Planeamiento | Borrador de discovery, arquitectura, ADRs y estructura del repo | Ajustar supuestos de negocio y alcance a cuotas de Free Edition | Docs en `docs/` |
| | | | | | |

## Patrones aprendidos
- _Ej.: la IA tiende a usar `collect()` en transformaciones; lo reemplazo por operaciones distribuidas._
