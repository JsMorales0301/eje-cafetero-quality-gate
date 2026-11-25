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

- **Revisión omitida:** un último commit de solo documentación (el registro de la revisión de la
  corrección, +11 líneas sobre el candidato ya aprobado) volvió a generar un candidato de riesgo
  medio. Gentle AI pidió consentimiento y elegí **omitir** la revisión de ese candidato.

### T3: capa gold (`feat/gold-aggregates`)

- **Prompt inicial:** Implementa la capa gold: `gold.precio_mensual` (precio promedio y número
  de observaciones por producto, ciudad y mes) y `gold.variacion_mensual` (variación porcentual
  contra el mes calendario anterior, nula si ese mes no existe). Debe construirse a partir de
  silver y poder reconstruirse sin duplicar. Escribe primero pruebas con valores calculados a
  mano y verifica contra los datos reales con un cálculo independiente en pandas.
- **Qué falló o faltó:** nada falló en las pruebas (RED por módulo inexistente, luego GREEN).
  En la verificación real, mi comparación independiente mostró una diferencia máxima de 0,01 en
  las variaciones y no quise atribuirla a redondeo sin comprobarlo; además mis dos primeros
  scripts de comprobación fallaron por mezclar `Decimal` con `float` al leer de Postgres.
- **Cómo lo reformulé:** recalculé las 1.222 variaciones en aritmética decimal con redondeo
  half-up, que es la convención de Postgres.
- **Resultado final:** 52 pruebas pasan. Con 5000 filas reales: 1.299 filas en
  `gold.precio_mensual` y 1.299 en `gold.variacion_mensual`; los promedios y conteos coinciden
  al 100 % con un cálculo independiente en pandas (0 filas sin pareja, la suma de observaciones
  es 5000 = filas de silver). Las variaciones coinciden exactamente con el cálculo decimal
  half-up; solo 1 fila difiere del redondeo en float de numpy, que es otra convención.
  Convenciones: una semana pertenece al mes de su fecha inicial, y la variación se mide contra
  el mes calendario anterior (nula si ese mes no tiene datos).
- **Revisión (Gentle AI):** riesgo medio (4 archivos, 222 líneas; cambio ejecutable en
  `src/pipeline/gold.py`). Consentí la revisión. Una lente aplicada: *reliability*. Resultado:
  **aprobada**, sin hallazgos bloqueantes. Hallazgos informativos, aún sin atender:
  - *WARNING* (`src/pipeline/gold.py:20-30`): gold asume que silver no tiene nulos y se
    reconstruye sin comprobar que el último gate pasó; tampoco hay prueba de que un fallo a
    mitad de la reconstrucción deje intacto el gold anterior.
  - *SUGGESTION* (`src/pipeline/gold.py:44-47`): la rama en la que el promedio del mes anterior
    es 0 (variación nula por la guarda) no tiene prueba.
  - *SUGGESTION* (`tests/test_gold_integration.py:33-36`): **el revisor tiene razón.** Mi
    fixture usa `fecha_final = fecha_inicial`, así que la prueba "la semana pertenece al mes de
    su fecha inicial" no ejercita una semana que cruce de mes y pasaría igual si se agrupara
    por fecha final. La convención está implementada, pero esa prueba no la demuestra.
- **Prompt de corrección (nuevo prompt, a partir de la revisión de Gentle AI):** Corrige los
  tres hallazgos informativos de la revisión de T3. Haz que el fixture tenga una semana que
  cruce de mes y demuestra con una mutación (agrupar por fecha final) que la prueba ahora
  discrimina. Agrega pruebas para el promedio previo en cero y para que un fallo a mitad de
  la reconstrucción deje intacto el gold anterior. No agregues una guarda de "el último gate
  pasó": comprueba en su lugar que silver rechaza nulos.
  - **Qué falló o faltó:** el hallazgo sobre la prueba de la semana era correcto y era un error
    mío. Durante la mutación hice un `git stash` innecesario y escribí un archivo temporal en
    `/tmp`; no dejaron residuos y lo revertí. Al refactorizar el fixture cambié sin necesidad
    el rango mínimo/máximo (de medio ± 10 a igual al medio), lo que la revisión señaló; lo
    restauré.
  - **Cómo lo reformulé:** la semana del 29 de enero ahora termina el 3 de febrero
    (`fecha_final = fecha_inicial + 5 días`, como en los datos reales).
  - **Resultado final:** con la mutación (agrupar por fecha final) fallan 3 pruebas; con la
    implementación real pasan. Las pruebas del promedio previo en cero, del rollback de gold y
    de que silver rechaza nulos se escribieron sobre comportamiento que ya existía, así que
    pasaron a la primera: son pruebas de caracterización, no de un defecto nuevo. No agregué
    la guarda del gate porque bloquearía reconstruir gold tras un lote rechazado, aunque silver
    siga siendo bueno. 55 pruebas pasan.
  - **Revisión (Gentle AI):** candidato parcial (1 archivo, 26 líneas; solo el arreglo del
    fixture). Consentí la revisión; una lente, *reliability*; **aprobada** sin bloqueantes. Dos
    observaciones menores: el cambio del rango mínimo/máximo (restaurado) y que el comentario
    de la prueba menciona el resultado por fecha final pero solo se afirma el de fecha inicial,
    lo que el revisor juzgó suficiente. Las pruebas añadidas después de esa revisión no se
    volvieron a revisar.

- **Revisión omitida:** el candidato de la rama completa de T3 contra `main` (4 archivos,
  294 líneas), que incluía las pruebas agregadas después de la última revisión, no se revisó:
  Gentle AI pidió consentimiento y elegí **omitir**.

### T4: orquestador y corrupción controlada (`feat/pipeline-cli`)

- **Prompt inicial:** Implementa `python -m pipeline.run`, que encadena extracción, bronze,
  quality gate, silver y gold, e informa en qué etapa falló y con qué código de salida (0 ok,
  1 el gate rechazó el lote, 2 otro error). Agrega una opción de origen (datos reales o la
  muestra local determinista) y un inyector de corrupción controlada y reproducible (nulos,
  duplicados, error de unidad, ceros de más, precios negativos, mínimo mayor que máximo,
  fechas inválidas, categoría mal escrita). Escribe primero las pruebas y demuestra que un lote
  corrupto no llega a silver ni a gold.
- **Qué falló o faltó:** las pruebas pasaron completas (83) a la primera tras implementar, y el
  RED inicial fue solo por módulos inexistentes. Tres desvíos que conviene saber: (1) en el plan
  había escrito `--source clean|corrupted`; al diseñarlo vi que mezclaba dos ideas (de dónde
  vienen los datos y si se corrompen), así que quedó `--source live|fixture` más `--corrupt`.
  (2) El error de unidad (todos los precios x10) no se detecta en la muestra de 30 filas
  (su media es baja), solo en un lote realista; por eso su prueba es estructural y su detección
  se verificó aparte con 5000 filas reales. (3) Para las reglas de orden de precios, el reporte
  del gate muestra `unexpected=None`: GX no entrega el conteo de filas en esas expectativas.
- **Cómo lo reformulé:** moví la muestra de `tests/fixtures/` a `data/sample/`, porque el código
  de producción no debe leer de `tests/`, y separé `ingest` en extraer y cargar para reutilizarlo.
- **Resultado final:** 83 pruebas pasan. Con datos reales por CLI: lote limpio de 5000 filas ->
  `RESULT OK bronze=5000 silver=5000 gold=1299`, exit 0; error de unidad -> el gate lo rechaza
  (`batch_mean.precio_medio` = 53.452), exit 1; nulos + duplicados + ceros de más -> 5 reglas
  falladas, exit 1; tipo de corrupción inexistente -> `failed stage=corrupt`, exit 2. Tras los
  lotes rechazados, silver sigue con el lote limpio (1 lote, 5000 filas) y gold con 1.299, y
  `meta.quality_runs` guarda cada ejecución.
- **Revisión (Gentle AI):** riesgo medio (15 archivos, 561 líneas; la evidencia señaló el CSV
  de muestra, que solo se movió de carpeta). Consentí la revisión. Una lente aplicada:
  *reliability*. Resultado: **aprobada**, sin hallazgos bloqueantes. Hallazgos informativos,
  aún sin atender:
  - *WARNING* (`src/pipeline/run.py:121-122`): `main()` calcula el límite de filas y crea la
    conexión **fuera** del bloque que informa la etapa. Un `SOCRATA_ROW_LIMIT` inválido o una
    configuración de base de datos ausente producen un traceback sin etapa y con **exit 1**, el
    mismo código que significa "el gate rechazó el lote". Esto contradice el contrato de códigos
    de salida que documenté y que Jenkins usará para distinguir fallos. **El revisor tiene
    razón.**
  - *SUGGESTION* (`src/pipeline/run.py`): ninguna prueba ejecuta `main()` de punta a punta, así
    que una regresión en el mapeo de códigos de salida o en la línea `RESULT` pasaría inadvertida.
  - *SUGGESTION* (`src/pipeline/corruption.py`): casos límite sin probar: `min_gt_max` cuando
    ningún lote tiene mínimo < máximo (falla con `ValueError`, exit 2), comparaciones con NaN,
    y `_scaled` descarta decimales en precios no enteros.
- **Prompt de corrección (nuevo prompt, a partir de la revisión de Gentle AI):** Corrige los
  tres hallazgos informativos de la revisión de T4. Un error de configuración (límite de filas
  inválido o variable de base de datos ausente) debe salir con exit 2 y nombrar su etapa, nunca
  con exit 1, que solo significa "el gate rechazó el lote". Agrega una prueba de `main()` de
  punta a punta para los códigos 0, 1 y 2 y la línea `RESULT`. Cubre los casos límite del
  inyector (sin filas elegibles, NaN, decimales) y corrige lo que falle. Escribe primero las
  pruebas.
  - **Qué falló o faltó:** el hallazgo principal era un error real de mi diseño: el contrato de
    códigos de salida que documenté no se cumplía antes de la primera etapa. Además, mi segunda
    demostración por CLI no valió: usé `POSTGRES_USER=` vacío, que no equivale a "ausente", y
    corrí con una imagen vieja que aún no tenía la muestra en `data/sample/`. Esa ausencia ya
    la cubre la prueba unitaria; la imagen reconstruida corre el flujo sin montar nada.
  - **Cómo lo reformulé:** moví la lectura del límite y la conexión a un bloque propio con etapa
    `config`; `SOCRATA_ROW_LIMIT` inválido da un mensaje claro y la variable ausente se nombra
    explícitamente. Los precios con decimales se formatean sin perder precisión.
  - **Resultado final:** de las pruebas nuevas, 3 fallaron primero (RED): los dos errores de
    configuración y el precio negativo con decimales (`-2050.5` salía como `-2050`). El resto
    (`main()` de punta a punta, casos límite de `min_gt_max`, NaN) se escribió sobre
    comportamiento que ya existía y pasó a la primera: son pruebas de caracterización. Ahora
    90 pruebas pasan; con `SOCRATA_ROW_LIMIT=abc` el CLI devuelve
    `RESULT FAILED stage=config exit=2`.
  - **Revisión (Gentle AI):** riesgo medio (16 archivos, 692 líneas; la rama completa de T4,
    incluida esta corrección). Consentí la revisión. Una lente aplicada: *reliability*.
    Resultado: **aprobada**, sin hallazgos bloqueantes y con una sola observación, aún sin
    atender: *SUGGESTION* (`src/pipeline/run.py:68-70`): un tipo de corrupción inexistente solo
    se rechaza dentro de la etapa `corrupt`, es decir, después de extraer; con `--source live`,
    un error de tipeo en `--corrupt` descarga primero toda la ventana de la API y recién
    entonces sale con exit 2. Validar los tipos al inicio ahorraría esa llamada de red. El
    comportamiento es correcto y está probado; es solo una mejora de robustez.
- **Segunda revisión (Gentle AI):** el último commit de documentación de T4 (+7 líneas) generó
  otro candidato de riesgo medio. Consentí y Gentle AI lo volvió a **aprobar**, sin bloqueantes.
  Repitió la sugerencia de validar `--corrupt` antes de extraer y agregó una nueva: ninguna
  prueba cubre que falte el archivo de muestra (lo atrapa el manejador genérico de la etapa
  `extract`, exit 2). Ambas siguen sin atender.

### T5: dashboard (`feat/dashboard`)

- **Prompt inicial:** Implementa el dashboard en Streamlit que lee solo la capa gold y el estado
  del quality gate. Debe mostrar el historial de ejecuciones del gate, la serie de precios por
  producto y ciudad, y una sección "qué pasaría sin el gate" que aplique una corrupción
  controlada al último lote aprobado, muestre si el gate la rechazaría y compare el ranking de
  mayores alzas con y sin el gate. Separa la lógica en funciones puras con pruebas, usa colores
  validados con indicador no cromático, y verifica en el navegador con una captura.
- **Qué falló o faltó:** (1) Mirar el resultado en el navegador encontró dos defectos que ninguna
  prueba veía: las etiquetas directas de las dos líneas se escribían una sobre otra, y las
  tablas lado a lado quedaban cortadas. (2) Un hallazgo de diseño: si todos los precios se
  multiplican por 10 (`unit_error`), el **porcentaje** de variación no cambia (la escala se
  cancela), así que el ranking de alzas solo se distorsiona con corrupciones parciales como
  `typo_zeros`; por eso la sección compara niveles y ranking. (3) Dos errores de mis pruebas:
  `AppTest` resuelve rutas relativas contra el archivo de la prueba, y asumí que `20156.5` se
  redondea a `20,157` cuando Python lo redondea al par (`20,156`). (4) El texto de la interfaz
  está en inglés, que es el idioma por defecto de los artefactos; si la docente lo prefiere en
  español, es un cambio de cadenas.
- **Cómo lo reformulé:** escribí primero las pruebas de ambos defectos visuales (las etiquetas se
  separan 20 px aunque las series terminen en el mismo valor; las tablas bajan a 4 columnas) y
  luego los corregí; ajusté las pruebas erróneas.
- **Resultado final:** 119 pruebas pasan. Verificado en el navegador con 5000 filas reales: el
  historial muestra los lotes aprobados y rechazados con sus reglas; con `typo_zeros` al 5 % el
  gate rechaza el lote (`price_order.maximo_gte_medio`, `price_plausible_range.precio_medio`) y
  226 de 1.299 promedios mensuales habrían cambiado. El ranking con datos aprobados lidera con
  Pitahaya +54,3 %; sin el gate aparece Manzana roja importada +2.305,3 % (falsa alarma) y la
  Pitahaya desaparece del top 5. Los puertos solo se publican en `127.0.0.1` y la telemetría de
  Streamlit está desactivada.
- **Revisión (Gentle AI):** **omitida.** Riesgo medio (13 archivos, 710 líneas; cambio de
  configuración en `Dockerfile`). Gentle AI pidió consentimiento para la rama completa de T5 y
  elegí **omitir**, así que el dashboard, sus consultas y sus pruebas no tuvieron una segunda
  mirada de Gentle AI. La verificación de T5 se apoya en las 119 pruebas y en la comprobación
  en el navegador.

### T6: README, diagramas e informe (`docs/readme-and-report`)

- **Prompt inicial:** Escribe el README para levantar el sistema y ejecutar la operación de
  ejemplo con su resultado esperado, anticipando los errores comunes; los diagramas de
  arquitectura y de flujo de datos; y un borrador del documento del Escenario 3 con espacios
  para mis capturas. Genera las salidas esperadas ejecutando los comandos de verdad, revisa los
  diagramas mirándolos, y comprueba el README en un clon limpio.
- **Qué falló o faltó:** (1) Mi primer intento de generar las salidas esperadas falló: el
  contenedor `db` no arrancó porque tu propio proyecto ya ocupaba los puertos 5433 y 8501, y mi
  `/dev/null` escondió el error. Ese choque es justo un error común, así que entró al README.
  (2) Los diagramas, al mirarlos, tenían etiquetas más anchas que el hueco entre cajas y cortaban
  los bordes con un recuadro blanco; un reemplazo con `re.sub` falló por secuencias de escape y
  el script siguió con la versión vieja sin avisar. (3) **Afirmé en el README que la falta de
  `.env` produce `missing environment variable`; era falso.** Al reproducirlo, Compose avisa
  `variable is not set. Defaulting to a blank string` y `db` termina con `Database is
  uninitialized and superuser password is not specified`. (4) Mi comprobación de la fila de
  Patilla usó un patrón con un espacio de menos y reportó un FALLO que era error mío.
- **Cómo lo reformulé:** corregí el espaciado de los diagramas y volví a mirarlos; reescribí la
  fila del README con el síntoma real; en lugar de usar un patrón a ojo, comparé el bloque del
  README contra la salida real línea por línea. Verifiqué en un clon limpio del commit, en un
  directorio con otro nombre para no chocar con tus contenedores en ejecución, y con un archivo de
  *override* sin puertos publicados solo por el choque de puertos.
- **Resultado final:** README con puesta en marcha, operación de ejemplo con resultado esperado,
  demostración de lote corrupto, variables, errores comunes, estructura y limitaciones; dos
  diagramas (Mermaid en el README y PNG para el informe); y un borrador del informe en Markdown
  y Word con cinco espacios para capturas. En el clon limpio: la operación de ejemplo dio
  exactamente las salidas del README (bronze 30, silver 30, gold 24; fila de Patilla
  `2090.00`; lote corrupto con exit 1 y silver intacto), 119 pruebas pasaron y el dashboard
  respondió `ok`. Los mensajes de "puerto ocupado", "no resuelve `db`" y "contraseña" también
  los vi en una ejecución real. **No verificado:** el paso de puertos del README se ejecutó con
  el *override*, no literalmente, por el choque con tu proyecto. Las **capturas** del informe las
  debes tomar tú, de tu propia máquina: son la evidencia de tu entorno.
- **Revisión (Gentle AI):** **omitida.** Riesgo medio (7 archivos, 446 líneas; la evidencia señaló
  una línea nueva en `.gitignore`). Gentle AI pidió consentimiento para la rama de T6, que es casi
  toda documentación, y elegí **omitir**. La afirmación más frágil de esa rama, el README, se
  verificó después ejecutándolo (ver T7).

### T7: validación final en carpeta limpia (`chore/clean-clone-validation`)

- **Prompt inicial:** Valida el Escenario 3 desde cero, como lo haría la docente: clona el
  repositorio público desde GitHub sin mis credenciales, comprueba que no haya secretos en los
  archivos ni en el historial, y sigue el README al pie de la letra, ejecutando cada comando
  exactamente como está escrito, para que se levante solo con el README. Luego compara cada
  resultado con lo que el README promete.
- **Qué falló o faltó:** (1) Mis contenedores en ejecución ocupaban los puertos 5433 y 8501, así
  que en T6 el paso de puertos no se pudo ejecutar literalmente; pedí permiso y apagué tus
  contenedores (`docker compose down`, sin `-v`, sin tocar tus datos) para poder hacerlo.
  (2) Si hubiera clonado en la carpeta con el nombre por defecto, Compose habría reutilizado
  tu volumen y la corrida habría reemplazado tus datos; por eso clonó en una carpeta con otro
  nombre, lo único que difiere del README. (3) Al revisar el informe encontré una afirmación mía
  que no podía sostener: que Great Expectations 1.x "no está disponible en versiones más nuevas
  de Python"; solo comprobé que con el Python 3.15 de tu equipo `pip` ofrece la 0.18.
- **Cómo lo reformulé:** cada comando se ejecuta solo si aparece textualmente en el README, para
  no transcribirlo mal; el informe ahora dice exactamente lo que se observó.
- **Resultado final:** desde GitHub, sin credenciales: el repositorio es público (página 200,
  `ls-remote` y `clone` anónimos); `.env` no está versionado ni lo estuvo nunca; el barrido de
  todo el historial no encontró contraseñas, tokens ni claves (solo el valor de ejemplo de
  `.env.example`); los 6 commits de un segundo nombre de autor son los 6 merges de PR. Los
  diagramas Mermaid y las tablas del README se dibujan bien en GitHub. Con el README al pie de la
  letra: `db` sano con el puerto 5433 publicado; operación de ejemplo (`bronze=30 silver=30
  gold=24`, Patilla `2090.00`, bloque idéntico al del README); lote corrupto con exit 1 y silver
  intacto; datos reales `bronze=5000 silver=5000 gold=1299`; dashboard respondiendo en
  `localhost:8501`; 119 pruebas pasan. Cierra el pendiente de T6 sobre el paso de puertos.
- **Revisión (Gentle AI):** pendiente; se registra aquí tras la revisión de este candidato.

### Ampliación del informe: APA 7, conceptos y contraste (`chore/clean-clone-validation`)

- **Prompt inicial (mío, textual):** "Revisa los requisitos de la entrega, tiene que ir en APA,
  coloquemos una sección donde expliquemos los conceptos de ingeniería de datos para que se
  entienda y cómo hace contraste el CI con el data ops".
- **Qué falló o faltó:** (1) Al releer las guías, el documento del Escenario 3 **no pide APA de
  forma explícita**; sí lo pide el Escenario 5 ("fuentes oficiales en APA 7"), y la lista de
  "Material de consulta" de cada guía está en APA. Se aplicó APA 7 de todos modos y se dejó una
  marca para confirmarlo con la docente. (2) La búsqueda web no devolvió el sitio oficial del
  DataOps Manifesto, solo resúmenes de terceros; en lugar de citar principios de memoria, se
  leyeron las páginas primarias de cada fuente. (3) Al leer el artículo de Fowler, la herramienta
  avisó de que parte de su contenido era un resumen no verificado; solo se usó lo leído
  textualmente (la definición y los títulos de las prácticas). (4) Se descartó una fuente
  (Ereth, 2018) porque no se pudo confirmar el nombre del autor. (5) Un script de comprobación
  mío falló por un error de formato en su última línea; no afectó al documento. (6) El formato
  no se pudo ver renderizado: se verificó leyendo la estructura del archivo.
- **Cómo lo reformulé:** cada afirmación atribuida a una fuente se apoya en lo verificado en su
  página primaria, y las interpretaciones propias se señalan como tales en el texto; el
  manifiesto se describe como documento de practicantes, creado y mantenido por una empresa, y se
  contrasta con un artículo arbitrado (Munappy et al., 2020).
- **Resultado final:** el informe ahora tiene portada y formato APA 7 (Times New Roman 12, doble
  espacio, sangría de primera línea, encabezados de nivel 1 centrados y en negrita, número de
  página arriba a la derecha, figuras y tablas rotuladas, referencias con sangría francesa), una
  sección de conceptos de ingeniería de datos, un contraste entre integración continua y DataOps
  con su relación con el proyecto, y 8 fuentes que corresponden una a una con sus citas.
  Plantilla de formato: `docs/apa-reference.docx`. Para regenerar el Word:
  `pandoc docs/informe-escenario-3.md -o docs/informe-escenario-3.docx --reference-doc=docs/apa-reference.docx --resource-path=docs`.
- **Revisión (Gentle AI):** pendiente.

### Corrección: instrucción de la Captura 1 del informe (`docs/clarify-capture-1`)

- **Prompt (mío, textual):** "Cuando hago el docker compose ps solo me aparece db" y, después,
  que ya había ejecutado `docker compose build app`, `docker compose up -d db` y
  `docker compose run --rm app python -m pipeline.run --source fixture`.
- **Qué falló o faltó:** el informe decía que `docker compose ps` debía mostrar `app` y `db`,
  pero esos tres comandos (la sección "Reproducción") no dejan `app` corriendo: `run --rm` crea un
  contenedor temporal que se borra al terminar. La instrucción era incompleta y es un error mío;
  el comportamiento del sistema era el correcto. Lo comprobé en tu máquina: solo existía el
  contenedor `db`, sano, y ningún contenedor `app`, ni siquiera detenido.
- **Cómo lo reformulé:** la Captura 1 ahora indica que primero hay que ejecutar
  `docker compose up -d app`, y la sección "Reproducción" aclara que solo deja corriendo la base.
- **Resultado final:** cambio solo de documentación; no cambió ningún comportamiento.
- **Revisión (Gentle AI):** pendiente.

### Dashboard en español (`feat/dashboard-es`)

- **Prompt (mío, textual):** "Vuelve el dashboard en español por favor".
- **Qué falló o faltó:** (1) En T5 dejé la interfaz en inglés, que es el idioma por defecto de los
  artefactos, y al cerrar T5 pregunté si la querías en español; no hubo respuesta y quedó en
  inglés. (2) **Las cifras que cité de T5 no eran reproducibles.** Al volver a abrir el dashboard
  traducido, la falsa alarma había cambiado (de "Manzana roja importada +2.305,3 %" a "Coco
  +2.396,7 %", y de 226 a 230 promedios cambiados). La causa: la simulación lee el último lote
  desde Postgres sin `ORDER BY`, y la corrupción con semilla fija elige filas por posición, así
  que el resultado dependía del orden físico en cada base de datos. Lo detecté al comparar mis
  capturas nuevas con las anteriores. (3) Mi primer intento de cargar datos para la captura
  falló sin avisar: en zsh, una variable sin comillas no se separa en palabras, así que el
  programa recibió `"--source live"` como un único argumento. (4) El panel del navegador estaba
  en modo oscuro y lo pasé a claro para que las capturas coincidieran con las anteriores.
  (5) Con las cifras nuevas, el informe quedó desactualizado: decía que la pitahaya "desaparece"
  del ranking, y ahora aparece con una cifra falsa.
- **Cómo lo reformulé:** primero las pruebas en español (RED), incluida una que exige que cada
  tipo de corrupción tenga su nombre en español; luego la traducción. Para la reproducibilidad,
  una prueba que lee el mismo lote guardado en dos órdenes distintos y exige el mismo resultado
  (falló primero), y después `ORDER BY` por todas las columnas fuente. Todo se verificó en un
  proyecto de Docker aparte, con otros puertos y su propia base, sin tocar tu base ni tus
  contenedores.
- **Resultado final:** 127 pruebas pasan. El dashboard está en español: títulos, métricas,
  tablas, gráficos, mensajes y los nombres de los tipos de corrupción (por ejemplo "Filas
  duplicadas"); los números siguen la convención española (coma decimal y punto de miles:
  `20.156`, `+54,3 %`) y los meses se rotulan en español (`ene 2023`, `jul 2023`). Con datos
  reales (5000 filas), la simulación da el mismo resultado en dos lotes distintos: sin el control
  encabeza el kiwi con +4.992,1 %, la pitahaya aparece con +3.921,5 % y 225 de 1.299 promedios
  cambian. El informe y el README se actualizaron con esas cifras y con 127 pruebas, y se
  reemplazaron las cuatro capturas del dashboard por otras de la versión en español. La
  afirmación de T5 de que la pitahaya "desaparece" del ranking no se sostiene con la simulación
  reproducible.
- **Revisión (Gentle AI):** en su momento **omitida** (candidato propio). Ese código quedó cubierto
  después por la revisión de la rama del Escenario 5, que partía de `main` (ver T9).

## Escenario 5: Jenkins

- **Prompt inicial (mío, textual):** "Ya tengo terminado el entregable de la semana 3, vamos con el
  de la semana 5". Antes de instalar nada, la IA revisó los requisitos y tu equipo y te preguntó
  si instalaba Jenkins con Homebrew (`jenkins-lts` y `openjdk@21`, servicio en el puerto 8080);
  respondiste: "Sí, instala Jenkins". El asistente de configuración de Jenkins, que pide crear el
  usuario administrador con una contraseña, queda como paso tuyo.
- **Plan:** T8 verificación de la operación, T9 `Jenkinsfile`, T10 instalar y configurar Jenkins,
  T11 falla provocada y corrección, T12 documento de requisitos en APA 7.

### T8: verificación de la operación de ejemplo (`feat/verify-operation`)

- **Prompt inicial:** Implementa `python -m pipeline.verify`, un comando que compare el resultado
  de la operación de ejemplo con un resultado esperado versionado y que termine con código distinto
  de cero si difiere, imprimiendo cada diferencia. Calcula los valores esperados de forma
  independiente del SQL. Escribe primero las pruebas.
- **Qué falló o faltó:** el entorno temporal de la sesión cambió de ruta y mi entorno de pandas
  quedó en la anterior, así que lo recreé. Las 17 pruebas pasaron a la primera tras implementar
  (el RED fue por módulo inexistente), por lo que su valor está en que las pruebas de manipulación
  (cambiar un precio, borrar filas, un lote rechazado) fallan como deben, no en haber descubierto un
  defecto.
- **Cómo lo reformulé:** los valores esperados (30 filas, 24 grupos mensuales y 3 promedios,
  dos de ellos con dos observaciones) salen de agrupar la muestra con pandas, no de consultar la
  base; así la verificación no se compara consigo misma.
- **Resultado final:** 144 pruebas pasan. Con el comando real: base vacía -> falla con 7
  diferencias; tras la operación limpia -> `VERIFY OK bronze=30 silver=30 gold=24 samples=3`,
  exit 0; tras un lote rechazado -> falla aunque *silver* conserve datos buenos, porque el último
  control no pasó (`bronze rows: expected 30, got 31` y `last quality gate run: expected passed,
  got rejected`), exit 1. Un archivo esperado inexistente es exit 2, no un fallo del resultado.
- **Revisión (Gentle AI):** cubierta por la revisión de la rama completa del Escenario 5 (ver T9):
  **aprobada**, sin hallazgos sobre `pipeline.verify`.

### T9: Jenkinsfile y override de CI (`feat/jenkinsfile`)

- **Prompt inicial:** Escribe el `Jenkinsfile` que obtiene el código, construye la imagen, levanta
  los dos contenedores, ejecuta la operación de ejemplo, verifica el resultado (que decida si pasa
  o falla) y retira todo aunque falle. Debe dispararse con Poll SCM, indicar en qué etapa falló,
  no guardar secretos en el repositorio y no chocar con mis contenedores. Escribe primero pruebas
  estructurales y simula la construcción antes de tener Jenkins configurado.
- **Qué falló o faltó:** (1) Una de mis 14 pruebas falló por un defecto de la propia prueba: buscaba
  el texto `set -x` en todo el bloque y mi comentario del `Jenkinsfile` lo menciona; la corregí para
  mirar solo el cuerpo del script de shell. (2) Las pruebas leen el `Jenkinsfile` desde la raíz del
  repositorio y la imagen no lo traía, así que copié los tres archivos de CI a la imagen para que
  `docker compose run --rm app pytest` las ejecute en vez de saltarlas en silencio. (3) **Lo que no
  está verificado:** la sintaxis Groovy y el comportamiento propio de Jenkins (los plugins
  *Timestamper* y *Pipeline*, `pollSCM`, `archiveArtifacts`, `currentBuild.description`). La
  simulación ejecuta los pasos de `sh`, no el Groovy; eso solo se comprueba cuando Jenkins corra la
  primera construcción.
- **Cómo lo reformulé:** escribí un simulador que lee el `Jenkinsfile` y ejecuta sus etapas y sus
  pasos `sh` en orden, con un `PATH` mínimo como el de un servicio de macOS, en un clon limpio, con
  un proyecto de Compose aparte, y que comprueba que la contraseña generada no aparece en la salida.
- **Resultado final:** 158 pruebas pasan. Simulación de una construcción normal: las seis etapas
  pasan (`RESULT OK bronze=30 silver=30 gold=24`, `VERIFY OK ...`), la contraseña no aparece en la
  salida y no queda ningún contenedor, volumen ni `.env`. Simulación con `CORRUPT=duplicates`:
  falla en "Operacion de ejemplo" con código 1, la verificación no se alcanza y el cierre limpia
  todo igual. El parámetro rechaza `duplicates; rm -rf /`, `$(id)`, mayúsculas y espacios antes de
  llegar al shell. Decisiones: `docker compose exec` en vez de `run`, para que la operación corra en
  el contenedor ya levantado; contraseña aleatoria por construcción, en lugar de una credencial
  guardada en Jenkins; sin puertos publicados, para no chocar con los contenedores de desarrollo.
- **Revisión (Gentle AI):** la revisión de la rama completa del Escenario 5 contra `main` (26
  archivos, 1029 líneas; la evidencia señaló `.gitignore`) cubrió T8, T9 y también el código del
  dashboard en español y la lectura determinista del lote, que habías omitido en su momento.
  Consentí la revisión. Una lente aplicada: *reliability*. Resultado: **aprobada**, sin hallazgos
  bloqueantes. Un hallazgo informativo (*WARNING*, `src/dashboard/charts.py:50-56`): con más de
  unos 8 años de datos mensuales, `_month_ticks` dejaba más de 8 marcas en el eje, porque el
  adelgazamiento solo se activaba si quedaban menos de 2. **Lo reproduje con una prueba (10 marcas
  con 10 años de datos) y lo corregí** (ahora el eje queda entre 2 y 8 marcas). Esa corrección la
  hice por iniciativa de la IA, sin un prompt nuevo tuyo, porque la rama aún no se había subido;
  no se volvió a revisar. El revisor también observó, sin levantar un hallazgo, que el informe del
  Escenario 3 dice 127 pruebas y el README 159: lo dejé así a propósito, porque el informe es un
  documento de la semana 3 y describe el proyecto en ese momento, no el estado actual.

### T10 a T12

Se completan al iniciar cada tarea, con el mismo formato que T2: prompt inicial, qué falló,
cómo lo reformulé, resultado final y revisión (Gentle AI).

## Errores de la IA detectados

| Qué dijo la IA | Qué mostró la salida real | Corrección |
|---|---|---|
| | | |
