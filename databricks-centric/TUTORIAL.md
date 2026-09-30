# Tutorial: probar Shark Knowledge v2 en Databricks Free Edition

Este tutorial te lleva de cero a validar el pipeline medallón
(Bronze → Silver → Gold) en Databricks Free Edition. Al final tendrás las 9
tablas Delta pobladas en Unity Catalog y habrás verificado los criterios de
aceptación "Data Ready".

---

## 0. Prerrequisitos

- Una cuenta de **Databricks Free Edition** (workspace creado).
- El código de este repo (carpeta `databricks-centric/`).
- Opcional: [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli) si
  prefieres subir por terminal en vez de por la UI.

> **Nota sobre Free Edition:** usa compute *serverless* y restringe el acceso
> saliente a internet por defecto. Lo verificamos en el Paso 1.

---

## 1. Smoke test (verificar el entorno antes de subir todo)

Antes de subir 26 archivos, confirma que tu workspace puede (a) instalar
paquetes, (b) salir a internet y (c) usar Unity Catalog.

1. En el workspace, crea un notebook nuevo (clic derecho → **New → Notebook**,
   lenguaje **Python**).
2. Pega y ejecuta estas celdas:

```python
# MAGIC %pip install pydantic requests
```

```python
import requests

r1 = requests.get(
    "https://en.wikipedia.org/api/rest_v1/page/summary/Great_white_shark",
    timeout=15,
)
r2 = requests.get(
    "https://api.gbif.org/v1/species/match",
    params={"name": "Carcharodon carcharias"},
    timeout=15,
)
print("Wikipedia status:", r1.status_code)
print("GBIF status:", r2.status_code)
```

```python
spark.sql("CREATE CATALOG IF NOT EXISTS shark_knowledge")
print([r.catalog for r in spark.sql("SHOW CATALOGS").collect()])
```

**Resultado esperado:** `200` en ambos `status_code` y `shark_knowledge` en la
lista de catálogos.

- Si Wikipedia/GBIF devuelven error de red → tu Free Edition no tiene salida a
  internet habilitada (ver *Solución de problemas*).
- Si `CREATE CATALOG` falla → Unity Catalog no está disponible en tu workspace
  (ver *Solución de problemas*).

---

## 2. Subir el código a Databricks

El proyecto tiene dos tipos de objetos, y Databricks los distingue por la
primera línea de cada archivo:

| Carpeta | Tipo en Databricks | Por qué |
| --- | --- | --- |
| `notebooks/*.py` | **Notebook** | empiezan con `# Databricks notebook source` |
| `src/*.py` | **File** (módulo importable) | NO tienen ese encabezado |

Es **crítico** que `src/` quede como *files* (no notebooks), porque los
notebooks los importan con `from src.pipeline import ...`.

### Método A — Databricks CLI (recomendado)

```bash
pip install databricks-cli
databricks auth login --host https://<tu-workspace>.cloud.databricks.com

# Sube toda la carpeta preservando la estructura
databricks workspace import-dir \
  ./databricks-centric \
  /Users/<tu-email>/databricks-centric \
  --overwrite
```

> Si tu versión del CLI convierte los `.py` de `src/` en notebooks (los verás
> con icono de notebook), usa el Método B para `src/`.

### Método B — UI manual

1. En el workspace, crea la carpeta `databricks-centric`.
2. Dentro, crea `src/` (con sus subcarpetas `config`, `resolver`, `bronze`,
   `silver`, `merge`, `gold`, `storage`) y `notebooks/`.
3. Para cada archivo de `src/`: clic derecho sobre su carpeta → **Import** →
   selecciona el archivo → **Import**. Databricks lo detecta como *file*.
4. Para cada archivo de `notebooks/`: clic derecho → **Import** → selecciona el
   archivo → se detecta como *notebook*.

**Verificación rápida:** en el workspace, los archivos de `src/` deben verse
como *files* (sin icono de notebook) y los de `notebooks/` como notebooks.

---

## 3. Ejecutar los notebooks (en orden)

### 3.1 `00_bootstrap` — instalación y creación de tablas

Abre `notebooks/00_bootstrap.py` y ejecuta **todas** las celdas.

Qué hace:
1. `%pip install pydantic requests`.
2. Detecta la ruta de `src/` y la agrega a `sys.path`.
3. Crea el catálogo `shark_knowledge`, los esquemas `bronze`/`silver`/`gold` y
   las 9 tablas Delta.

**Resultado esperado:** `Bootstrap complete: catalog/schemas/tables ready.`

Si falla el import de `src`, ver *Solución de problemas* (punto 3).

### 3.2 `01_run_pipeline` — procesar el lote semilla (18 especies)

Abre `notebooks/01_run_pipeline.py` y ejecuta todas las celdas.

Qué hace: llama `run_pipeline(SEED_SCIENTIFIC_NAMES, batch_id="seed_batch_01")`,
que consulta Wikipedia + GBIF y escribe Bronze (append), Silver (MERGE) y Gold
(MERGE).

**Resultado esperado** (aproximado, depende de las APIs en vivo):

```json
{
  "bronze": {"wikipedia": 18, "gbif_taxonomy": 18, "gbif_occurrence": 18},
  "silver": {
    "wikipedia_valid": 18, "wikipedia_rejected": 0,
    "gbif_taxonomy_valid": 18, "gbif_taxonomy_rejected": 0,
    "gbif_occurrence_valid": 484, "gbif_occurrence_rejected": 416
  },
  "rejected_records": 416,
  "gold": {"species": 18, "chunks": 149}
}
```

### 3.3 `02_verify_data` — criterios de aceptación

Abre `notebooks/02_verify_data.py` y ejecuta todas las celdas.

Verifica:
- Las 9 tablas existen y tienen filas.
- `gold.species` tiene **exactamente 18** filas.
- Cada especie tiene ≥ 1 chunk.
- **Rerun converge**: re-ejecuta el lote y comprueba 0 especies nuevas, 0 chunks
  nuevos y 0 cambios de `content_hash`.

**Resultado esperado:** los tres `PASS` al final.

### 3.4 `03_ad_hoc` — especie fuera del lote semilla

Procesa `Carcharhinus amblyrhynchos` (tiburón gris de arrecife) solo con su
nombre científico. Verifica que entra a Gold con `origin = 'AD_HOC'`.

### 3.5 `04_quarantine` — cuarentena

Procesa `Nonexistentus sharkus` (sin artículo en Wikipedia). Verifica que **no**
entra a Gold y que el rechazo queda en `silver.rejected_records`.

---

## 4. Qué validaste al final

- Bronze/Silver/Gold persistidos como tablas Delta gobernadas en Unity Catalog.
- 18 especies aceptadas en `gold.species`.
- Idempotencia content-aware (rerun → 0 cambios lógicos).
- Especies ad-hoc sin editar ninguna lista maestra.
- Cuarentena explícita e inspeccionable.

Esto corresponde a los criterios "Data Ready" de la sección 19 del spec v2.

---

## 5. Solución de problemas

### 1. Wikipedia/GBIF no responden (sin salida a internet)

Free Edition restringe el tráfico saliente. Opciones:
- Verifica en la consola de administración si puedes habilitar el acceso a
  internet para el workspace.
- Si no es posible, el pipeline no puede consultar las APIs en vivo; necesitarás
  un workspace con salida a internet (o inyectar datos de prueba en Bronze).

### 2. `CREATE CATALOG` falla

- Confirma que Unity Catalog está habilitado (workspaces nuevos lo están por
  defecto desde nov-2023).
- Si tu Free Edition no lo soporta, cambia el catálogo a `hive_metastore`:
  en `src/config/seed_species.py` reemplaza `CATALOG = "shark_knowledge"` por
  `CATALOG = "hive_metastore"` y vuelve a subir `src/`.

### 3. `Could not import the src/ modules`

Causa típica: `src/*.py` se subió como *notebooks* en vez de *files*.
- Borra los archivos de `src/` del workspace y re-impórtalos como *files*
  (Método B, o CLI con `--format AUTO`).
- O setea `SRC_ROOT` manualmente en `00_bootstrap` con tu ruta real:
  `SRC_ROOT = "/Workspace/Users/<tu-email>/databricks-centric"`.

### 4. `MERGE ... UPDATE SET *` falla

Algunas versiones de runtime no soportan `UPDATE SET *`. Si ves ese error,
avísame y lo cambio por una lista explícita de columnas en
`src/storage/delta.py`.

### 5. `delta.enableRowTracking` no soportado

Si la creación de `gold.species_chunks` falla por la propiedad
`delta.enableRowTracking`, quítala de la DDL en `src/storage/delta.py` (es
opcional para Data Ready; solo prepara el futuro AI Search).
