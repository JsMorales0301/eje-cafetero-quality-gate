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

### T2 a T12

Se completan al iniciar cada tarea, con el mismo formato que T1.

## Errores de la IA detectados

| Qué dijo la IA | Qué mostró la salida real | Corrección |
|---|---|---|
| | | |
