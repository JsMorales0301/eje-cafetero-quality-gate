---
title: "Proyecto en dos contenedores comunicados con Docker"
subtitle: "Escenario 3: pipeline de datos con quality gate (Eje Cafetero)"
---

**Autor:** [Tu nombre completo y código]

**Curso:** Integración Continua

**Fecha:** [fecha de entrega]

## 1. Repositorio

<https://github.com/JsMorales0301/eje-cafetero-quality-gate>

Repositorio público con el código, el Dockerfile, el `docker-compose.yml` (dos contenedores y su
red), el README para levantar el sistema y ejecutar la operación de ejemplo, y los commits del
trabajo.

## 2. Qué hace el proyecto

Es un pipeline de datos de punta a punta: extrae precios mayoristas de alimentos del Eje
Cafetero desde datos.gov.co, valida su calidad, los carga por capas (bronze, silver, gold) y los
muestra en un dashboard.

La idea central que demuestra es **cómo un dato corrupto puede dañar decisiones y dar falsas
expectativas si no pasa pruebas de calidad.** Con datos aprobados, el mayor aumento de precio real
del último mes es Pitahaya (+54,3 %). Si un lote con ceros de más en el 5 % de las filas se saltara
el control, aparecería Manzana roja importada con +2.305 % (una falsa alarma) y la Pitahaya real
desaparecería del ranking. Con el control de calidad, ese lote se rechaza y el dashboard nunca lo
ve.

## 3. Qué hace cada contenedor

| Contenedor | Imagen | Función |
|---|---|---|
| `app` | Dockerfile propio sobre `python:3.12-slim` | Extrae los datos, ejecuta el control de calidad (Great Expectations), carga las capas y sirve el dashboard (Streamlit, puerto 8501). |
| `db` | `postgres:16-alpine` (imagen oficial) | Guarda las capas `bronze`, `silver`, `gold` y la auditoría `meta`. Tiene un *healthcheck* con `pg_isready`. |

**Por qué estas imágenes.**
`postgres:16-alpine` es la imagen oficial de la base de datos: no hay que mantener un Dockerfile
para ella, y la variante Alpine es pequeña. `python:3.12-slim` es la base del contenedor propio:
se fijó la versión 3.12 porque con el Python 3.15 de mi equipo `pip` solo ofrecía Great
Expectations 0.18, mientras que con 3.12 ofrece la 1.25 que usa el proyecto (se comprobó
consultando `pip index versions`), y `slim` evita paquetes que no se usan. El contenedor corre
con un usuario sin privilegios y las dependencias están fijadas con versión exacta.

## 4. Cómo se comunican

![Arquitectura: dos contenedores comunicados por nombre de servicio](images/architecture.png)

Los dos servicios están en la misma red de Docker Compose (`pipeline-net`). `app` encuentra a `db`
**por el nombre del servicio** (`host=db`, puerto 5432), no por una IP fija; Docker resuelve ese
nombre con su DNS interno.

**Orden de arranque.** `app` declara `depends_on` de `db` con la condición `service_healthy`:
Compose no arranca `app` hasta que `pg_isready` confirma que PostgreSQL acepta conexiones. Sin
esa condición, `app` podría intentar conectar mientras la base todavía se inicia.

**Credenciales.** Van en un archivo `.env` que no se sube al repositorio; el README indica qué
variables crear (`.env.example`). Los puertos publicados (8501 y 5433) escuchan solo en
`127.0.0.1`.

## 5. Flujo de datos

![Flujo de datos y compuerta de calidad](images/data-flow.png)

El lote crudo entra a **bronze** sin tocarlo. El **quality gate** aplica 22 expectativas (nulos,
rangos de precio, orden mínimo ≤ medio ≤ máximo, fechas, categorías, ciudades, clave única y
promedio del lote). Si pasa, se tipa en **silver** y se agrega en **gold**; si no, el lote se
rechaza, **silver y gold conservan el último lote aprobado** y la ejecución queda registrada con
las reglas que fallaron.

## 6. Cómo reproducirlo

Resumen (el detalle y los errores comunes están en el README del repositorio):

```bash
git clone https://github.com/JsMorales0301/eje-cafetero-quality-gate.git
cd eje-cafetero-quality-gate
cp .env.example .env            # y cambia POSTGRES_PASSWORD
docker compose build app
docker compose up -d db
docker compose run --rm app python -m pipeline.run --source fixture
```

## 7. Evidencias

> **Instrucciones (borrar antes de entregar):** reemplaza cada recuadro por una captura real de tu
> terminal o navegador. Compara con el "resultado esperado" que aparece debajo.

**Captura 1. Contenedores en ejecución.** Comando: `docker compose ps`.
Debe verse `app` y `db` con estado `Up`, y `db` en `healthy`.

[PEGAR CAPTURA 1]

**Captura 2. Guardar un dato.** Comando:
`docker compose run --rm app python -m pipeline.run --source fixture`.
Resultado esperado: `RESULT OK bronze=30 silver=30 gold=24`.

[PEGAR CAPTURA 2]

**Captura 3. Consultar el dato (los dos contenedores trabajando juntos).** Comando:
`docker compose exec db psql -U pipeline -d canasta -c "SELECT producto, ciudad, mes, precio_promedio, observaciones FROM gold.precio_mensual WHERE producto = 'Patilla';"`.
Resultado esperado: una fila, `Patilla | Pereira | 2024-03-01 | 2090.00 | 1`.

[PEGAR CAPTURA 3]

**Captura 4. Un lote corrupto es bloqueado.** Comando:
`docker compose run --rm app python -m pipeline.run --source fixture --corrupt duplicates`.
Resultado esperado: `RESULT FAILED stage=quality_gate exit=1`.

[PEGAR CAPTURA 4]

**Captura 5. Dashboard.** Abrir <http://localhost:8501> (con `--source live` cargado) y capturar la
sección "What would the dashboard show without the gate?" con `typo_zeros`: el gate rechaza el
lote y las dos tablas de mayores aumentos difieren.

[PEGAR CAPTURA 5]

## 8. Registro de uso de IA

**Herramienta.** Claude Code Desktop (modelo Claude Sonnet 5.5), configurado con Gentle AI
(instrucciones, skills y memoria persistente sobre el mismo modelo; no es otro modelo). La
revisión de cada cambio de riesgo medio o alto la realiza Gentle AI, con mi consentimiento por
cambio.

**Regla de verificación.** Todo resultado propuesto por la IA se ejecutó en mi entorno y se
contrastó con la salida real antes de aceptarlo.

**Para qué se usó y cómo evolucionaron los prompts.** Cada tarea tuvo un prompt inicial y, cuando
la revisión o la verificación encontraron fallos, un prompt de corrección. El registro completo
está en [`docs/ai-log.md`](https://github.com/JsMorales0301/eje-cafetero-quality-gate/blob/main/docs/ai-log.md).

| Tarea | Prompt inicial (resumen) | Qué hubo que corregir | Revisión de Gentle AI |
|---|---|---|---|
| T1. Extracción y bronze | Extraer de la API con paginación y cargar crudo a bronze. | Un helper de mis pruebas desplazaba columnas. | No se ejecutó. |
| T2. Silver y quality gate | Tipar, validar con Great Expectations y bloquear lotes malos. | Las pruebas borraban el silver real; un fallo de carga no quedaba auditado. | Aprobada dos veces; un candidato de solo documentación se omitió. |
| T3. Capa gold | Agregados mensuales y variación, comprobados contra pandas. | Una prueba de la semana no demostraba lo que decía. | Aprobada dos veces; la rama final se omitió. |
| T4. Orquestador | `pipeline.run` con códigos de salida y corrupción reproducible. | Un error de configuración salía con el mismo código que el gate. | Aprobada dos veces. |
| T5. Dashboard | Streamlit sobre gold con "qué pasaría sin el gate". | Etiquetas superpuestas y tablas cortadas, vistas solo al abrir el navegador. | Se omitió. |

**Errores de la IA detectados.** El detalle de cada uno (qué dijo la IA, qué mostró la salida real
y cómo se corrigió) está en `docs/ai-log.md`. Los más relevantes: una prueba "x10" que en realidad
multiplicaba por 1000, una comprobación de "silver intacto" que salió débil porque la suite
anterior ya lo había vaciado, y un contrato de códigos de salida que no se cumplía antes de la
primera etapa.

## 9. Limitaciones

- El control de calidad no detecta todo: si solo se infla `precio_maximo` conservando el orden y el
  rango plausible, el lote pasa. Un control reduce el riesgo, no lo elimina.
- Un error de unidad (todos los precios por 10) no se detecta en la muestra de 30 filas, pero sí en
  un lote realista de 5000 filas.
