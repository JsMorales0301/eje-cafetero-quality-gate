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
completan los otros tres campos y el campo **Revisión**.

**Revisión:** la revisión del cambio la realiza **Gentle AI** (revisión nativa por receipt-driven
development, con consentimiento explícito del autor para cada cambio de riesgo medio o alto).
Se registra aquí el riesgo asignado, las lentes aplicadas, el resultado y los hallazgos. Si el
autor omite la revisión de un cambio, se anota que se omitió.

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
- **Revisión (Gentle AI):** riesgo medio (10 archivos, 630 líneas; cambio ejecutable en
  `src/pipeline/promote.py`). Consentí la revisión. Una lente aplicada: *reliability*.
  Resultado: **aprobada**, sin hallazgos bloqueantes. Hallazgos informativos, atendidos
  después con un nuevo prompt (ver "Prompt de corrección"):
  - *WARNING* (`tests/test_promote_integration.py:18`): la limpieza de las pruebas de
    integración ejecuta `TRUNCATE silver.precios` sobre la base a la que apunte el entorno, por
    lo que correrlas contra la base real borra el silver vigente. Silver se regenera con
    `pipeline.promote`.
  - *SUGGESTION* (`src/pipeline/promote.py:58-65`): si la carga a silver falla en un lote que
    pasó el gate, la transacción se revierte y no queda fila en `meta.quality_runs`.
- **Prompt de corrección (nuevo prompt, a partir de la revisión de Gentle AI):** Corrige los
  dos hallazgos informativos de la revisión de Gentle AI sobre T2. (1) Las pruebas de
  integración no deben tocar la base real: aíslalas en una base de datos de test. (2) Si la
  carga a silver falla en un lote que pasó el gate, el fallo debe quedar registrado en
  `meta.quality_runs`. Escribe primero las pruebas que reproduzcan cada hallazgo, corrígelos y
  demuestra que el silver real no cambia al correr la suite.
  - **Qué falló o faltó:** mi primera comprobación de "silver real intacto" fue débil: silver
    ya estaba en 0 filas porque la suite anterior, sin aislamiento, lo había vaciado (el
    hallazgo en acción). Además, en mi primer borrador de la corrección llamé a `_record_run`
    con un engine en lugar de una conexión; lo detecté al releer, antes de ejecutarlo.
  - **Cómo lo reformulé:** cargué 5000 filas reales en silver antes de correr la suite y
    verifiqué que seguían ahí después; corregí `_record_run` para usar una conexión.
  - **Resultado final:** las dos pruebas nuevas fallaron primero (RED) por la razón esperada.
    Ahora la suite corre en una base `canasta_test` creada bajo demanda con el mismo esquema, y
    un fallo de carga queda registrado como `silver_load_error` en `meta.quality_runs`, deja
    silver con el último lote bueno y se vuelve a lanzar. 45 pruebas pasan. Silver real: 5000
    filas antes y después de la suite.
  - **Revisión (Gentle AI):** riesgo medio (12 archivos, 763 líneas; cambio de configuración en
    `Dockerfile`). Consentí la revisión. Una lente aplicada: *reliability*. Resultado:
    **aprobada**, sin hallazgos bloqueantes. Hallazgos informativos, aún sin atender:
    - *WARNING* (`src/pipeline/promote.py:58-76`): si la carga falla y además falla el registro
      de auditoría (por ejemplo, se pierde la conexión), el fallo solo se imprime en stderr y no
      queda fila en `meta.quality_runs`; la brecha de auditoría se cierra solo en parte.
      Tampoco hay prueba de que reintentar un lote tras un fallo de carga deje dos filas
      (fallida y luego aprobada).
    - *SUGGESTION* (`src/pipeline/promote.py:55-60`): ninguna prueba verifica que los tipos
      (fechas como fechas, manejo de NaN) sobrevivan el viaje a Postgres; solo se comprueban
      conteos e ids de lote.
    - *SUGGESTION* (`tests/test_promote_integration.py`): las pruebas de promoción no fijan la
      fecha de hoy, así que la regla de fechas plausibles depende del reloj real.

### T3 a T12

Se completan al iniciar cada tarea, con el mismo formato que T2: prompt inicial, qué falló,
cómo lo reformulé, resultado final y revisión (Gentle AI).

## Errores de la IA detectados

| Qué dijo la IA | Qué mostró la salida real | Corrección |
|---|---|---|
| | | |
