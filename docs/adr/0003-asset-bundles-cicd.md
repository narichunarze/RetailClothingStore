# ADR-0003 · Databricks Asset Bundles + GitHub Actions para CI/CD

- **Estado:** aceptada
- **Fecha:** 2026-11-25

## Contexto
El cliente (TI) exige despliegues reproducibles y revisables. Free Edition ofrece un solo workspace.

## Decisión
- Definir pipelines, jobs y permisos en `databricks.yml` + `resources/*.yml`.
- Targets `dev` y `prod` separados por **schema** (`andesmart_dev`, `andesmart_prod`).
- GitHub Actions: en PR → `ruff` + `pytest` + `bundle validate`; en merge a `main` → `bundle deploy -t prod`.

## Alternativas consideradas
- **Terraform:** más adecuado para infraestructura de workspace/cuenta, excesivo para el alcance.
- **Deploy manual desde la UI:** no reproducible, no auditable.

## Consecuencias
- (+) Todo versionado; mismo código en dev y prod.
- (−) En un cliente real dev/prod deberían ser catálogos o workspaces distintos; aquí se documenta como limitación de Free Edition.
