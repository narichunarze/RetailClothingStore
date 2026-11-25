# ADR-0004 · Tareas del job como wheel desde un Volume, no como imports del workspace

- **Estado:** aceptada
- **Fecha:** 2026-11-25

## Contexto
Los notebooks del job hacían `sys.path.append(<bundle>/files)` e importaban `src.*` desde `/Workspace/Users/.../.bundle/...`. En dev y en prod, el job falló varias veces con `OSError: [Errno 5] Input/output error` al leer un `.py` distinto cada vez (`train.py`, `quality.py`, `replenishment.py`), y el reintento a los 60 s también falló.

- La primera hipótesis fueron deploys concurrentes pisando archivos. Era parcial: se corrigió en el CI encolando los deploys, pero el error volvió en dev sin ningún deploy en paralelo.
- La comunidad de Databricks reporta el mismo error intermitente del FUSE del workspace (rutas `.bundle` incluidas), sin una solución oficial.

## Decisión
- `src/` se empaqueta como wheel (`pyproject.toml`). El bundle lo construye en cada deploy (`artifacts`, con `dynamic_version` para evitar caché) y lo sube a un **Volume de UC** (`workspace.artifact_path`).
- Las tareas del job son `python_wheel_task`, con entry points en `src/entrypoints.py` y un entorno serverless que instala el wheel, más versiones fijas de scikit-learn y MLflow.

## Alternativas consideradas
- **Más reintentos:** no ataca la causa, y el reintento ya fallaba.
- **Copiar `src/` a `/tmp` al inicio:** igual lee del FUSE del workspace.
- **Instalar el wheel desde el workspace:** mismo almacenamiento problemático.

## Consecuencias
- (+) Las tareas no dependen del FUSE del workspace. El código queda versionado como artefacto, que es la práctica estándar en producción.
- (+) Versiones fijas de scikit-learn y MLflow: entrenamiento y carga del modelo reproducibles.
- (−) Hay que crear el Volume `artifacts` en cada schema, y el deploy necesita Python para construir el wheel.
- (−) **El pipeline todavía importa `src.transforms` desde el workspace** (no falló hasta ahora). Si fallara, el siguiente paso es declarar el wheel como dependencia del entorno del pipeline.
