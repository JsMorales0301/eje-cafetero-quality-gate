# Registro de uso de IA

## Herramienta

- **Claude Code Desktop** (modelo Claude Sonnet 5.5), configurado con **Gentle AI**
  (instrucciones, skills y memoria persistente Engram sobre el mismo modelo).
  Gentle AI no es otro modelo: el contenido lo genera Claude.

## Regla de verificación

Todo resultado propuesto por la IA se ejecutó en mi entorno y se contrastó con la
salida real (terminal, capturas) antes de aceptarlo.

## Para qué se usó

| Fecha | Tarea | Qué generó la IA | Cómo lo verifiqué |
|---|---|---|---|
| 2026-11-24 | Selección de dataset | Búsqueda y perfilado de `gdqq-rry2` (datos.gov.co) | Descarga real: 83.813 filas, 0 nulos, 0 duplicados |
| | | | |

## Evolución de los prompts principales

### Prompt 1: definición del proyecto

- **Prompt inicial:** pipeline de datos (extracción hasta dashboard) para explicar cómo un
  dato corrupto daña decisiones; elegir herramientas, proyecto y dataset.
- **Resultado:** stack Python + Great Expectations + PostgreSQL + Streamlit + Docker
  Compose; dataset de precios del Eje Cafetero.
- **Qué ajusté:** pedí dividir el ETL en capas bronze, silver y gold.

### Prompt 2: planeación

- **Prompt:** planear lo que cubre hasta el Escenario 3 y después el Escenario 5.
- **Resultado:** plan de 12 tareas (T1 a T7 para el Escenario 3, T8 a T12 para el Escenario 5),
  una rama y un PR por tarea.

## Prompt inicial por tarea

Regla: antes de empezar cada tarea se escribe aquí el prompt inicial. Al terminarla se
completan los otros tres campos.

### T1: extracción y capa bronze (`feat/bronze-extraction`)

- **Prompt inicial:** Implementa la extracción desde la API Socrata del dataset `gdqq-rry2`
  con paginación y una ventana fija de datos, y la carga cruda a `bronze.precios_raw` con
  `_batch_id`, `_source_url` y `_ingested_at`. Incluye un CSV pequeño de prueba en el
  repositorio y pruebas unitarias. Verifica que el conteo en bronze coincida con el origen.
- **Qué falló o faltó:** con las pruebas escritas primero, la corrida inicial falló por import
  (esperado). Tras implementar, 1 de 12 pruebas falló: el generador de CSV falso de mi propia
  prueba no entrecomillaba campos con coma, y los valores se desplazaban. El error estaba en
  la prueba, no en el extractor.
- **Cómo lo reformulé:** corregí el helper para entrecomillar todos los campos y repetí la
  corrida.
- **Resultado final:** 12 pruebas pasan, incluida una de integración contra Postgres real.
  Ingesta real contra la API: 5000 filas en bronze con el mismo conteo que el origen
  (`bronze OK ... rows=5000`). Las fechas y precios quedan como texto crudo.

### T2: silver y quality gate (`feat/silver-quality-gate`)

- **Prompt inicial:** Implementa la capa silver y el quality gate con Great Expectations.
  Parsea las fechas en español, tipa los precios y valida nulos, tipos, rangos de precio,
  orden mínimo <= medio <= máximo, orden de fechas, categorías y ciudades válidas, claves
  duplicadas y un promedio plausible del lote. Si el lote no pasa, no debe tocar silver y
  debe quedar registrado en `meta.quality_runs`. Silver refleja el último lote aprobado.
  Calibra las reglas contra los datos reales y verifica con un lote limpio (pasa) y con
  lotes corruptos (rechazados).
- **Qué falló o faltó:** (1) Great Expectations 1.25 lanzó `DataContextRequiredError`: la suite
  necesita un contexto activo antes de agregar expectativas, y mi código lo creaba después.
  (2) Una prueba mía se llamaba "x10" pero multiplicaba por 1000; al corregirla a x10, el
  fixture de 30 filas (productos baratos) no superaba el umbral de media del lote.
  (3) Al perfilar el gate contra datos reales encontré un punto ciego: multiplicar solo
  `precio_maximo` por 10 no se detecta.
- **Cómo lo reformulé:** creé el contexto antes de la suite; renombré y ajusté la prueba a
  lo que el fixture demuestra (x100) y verifiqué x10 aparte con el lote real de 5000 filas;
  dejé el punto ciego como prueba documentada en vez de inventar una regla ajustada a ojo.
- **Resultado final:** 43 pruebas pasan. El gate acepta las 83.813 filas reales (0 falsos
  positivos) y rechaza nulos, duplicados, categorías inválidas, precios fuera de rango,
  orden mínimo/medio/máximo y error de unidad en todo el lote. Prueba de punta a punta:
  lote limpio -> `quality gate PASSED`, 5000 filas en silver; lote corrupto -> `FAILED`
  (`key_unique`, `batch_mean.precio_medio`), exit code 1, silver intacto y ambas ejecuciones
  en `meta.quality_runs`.

### T3 a T12

Se completan al iniciar cada tarea, con el mismo formato que T1.

## Errores de la IA detectados

| Qué dijo la IA | Qué mostró la salida real | Corrección |
|---|---|---|
| | | |
