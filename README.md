# RetailClothingStore · Lakehouse para retail de ropa (simulación FDE en Databricks)

Simulación de un engagement de **Forward Deployed Engineer** completo: discovery con el negocio → arquitectura → desarrollo AI-first → CI/CD → producción, en Databricks.

**Problema:** una cadena de tiendas de ropa pierde ventas por quiebres de tallas, liquida sobre-stock al final de temporada y consolida reportes a mano.
**Solución:** lakehouse medallion gobernado con Unity Catalog, KPIs de quiebre de stock por talla, forecast de demanda con MLflow, sugerencias de reposición y una capa de preguntas en lenguaje natural (Genie).

## Documentación
1. [Discovery: problema, stakeholders, user stories, KPIs](docs/01-discovery.md)
2. [Arquitectura](docs/02-architecture.md)
3. [Decisiones (ADRs)](docs/adr/)
4. [Plan de trabajo](docs/03-plan.md)
5. [Datos fuente](docs/04-source-data.md)
6. [Dashboard](docs/05-dashboard.md)
7. [Orquestación y CI/CD](docs/06-cicd.md)
8. [Forecast y reposición](docs/07-forecast.md)
9. [AI Log](AI_LOG.md)

## Stack
Databricks Free Edition · Lakeflow Declarative Pipelines · Auto Loader · Delta Lake · Unity Catalog · Lakeflow Jobs · MLflow · AI/BI Dashboards · Genie · Databricks Asset Bundles · GitHub Actions · PySpark · SQL

## Estructura
```
databricks.yml          # bundle: targets dev/prod
resources/              # definición de pipelines y jobs
src/
  data_gen/             # generador de datos sintéticos + APIs externas
  pipelines/            # bronze / silver / gold
  ml/                   # forecast y reposición
  agent/                # capa de IA (Genie / agente)
tests/                  # pytest de transformaciones
docs/                   # discovery, arquitectura, ADRs, plan
```

## Quickstart
```bash
pip install -r requirements-dev.txt
pytest
databricks auth login --host <tu-workspace-url>
databricks bundle validate -t dev
databricks bundle deploy -t dev
```

## Estado
🚧 Fase 1 — generador de datos listo; falta subirlo a Databricks. Ver [plan](docs/03-plan.md).
