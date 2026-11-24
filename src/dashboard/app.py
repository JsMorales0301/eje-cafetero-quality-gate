"""Panel de Streamlit. Lee solo la capa gold y el registro de auditoría del control de calidad."""
import pandas as pd
import streamlit as st

from dashboard import data
from dashboard.charts import price_figure
from dashboard.labels import KIND_LABELS
from dashboard.tables import risers_table
from dashboard.whatif import price_risers, simulate
from pipeline.corruption import KINDS
from pipeline.db import get_engine

KEYS = ["producto", "ciudad", "mes"]

st.set_page_config(page_title="Eje Cafetero: control de calidad", layout="wide")
st.title("Precios de alimentos en el Eje Cafetero: qué protege un control de calidad")
st.caption("Precios mayoristas semanales de datos.gov.co (RAP Eje Cafetero). Todo lo que aparece "
           "en las dos primeras secciones proviene de lotes que pasaron el control de calidad.")

engine = get_engine()
if not data.has_approved_data(engine):
    st.info("Todavía no hay datos aprobados. Ejecuta `python -m pipeline.run` para cargar un lote.")
    st.stop()

# --- 1. Control de calidad -------------------------------------------------------------
st.subheader("Control de calidad")
runs = data.quality_runs(engine)
passed = int(runs["passed"].sum())
a, b, c = st.columns(3)
a.metric("Última ejecución", "✅ aprobado" if runs.loc[0, "passed"] else "⛔ rechazado")
b.metric("Lotes aprobados", passed)
c.metric("Lotes rechazados", len(runs) - passed)
shown_runs = runs.assign(resultado=runs["passed"].map({True: "✅ aprobado", False: "⛔ rechazado"}))
shown_runs = shown_runs.rename(columns={"executed_at": "fecha", "batch_id": "lote",
                                        "rows_checked": "filas",
                                        "failed_rules": "reglas que fallaron"})
st.dataframe(shown_runs[["fecha", "lote", "resultado", "filas", "reglas que fallaron"]],
             hide_index=True, use_container_width=True)

# --- 2. Precios (gold) -----------------------------------------------------------------
st.subheader("Precios (capa gold)")
options = data.products_and_cities(engine)
left, right = st.columns(2)
product = left.selectbox("Producto", sorted(options["producto"].unique()), key="product")
cities = sorted(options.loc[options["producto"] == product, "ciudad"])
city = right.selectbox("Ciudad", cities, key="city")
approved_series = data.price_series(engine, product, city)
st.plotly_chart(price_figure(approved_series), use_container_width=True)

st.markdown("**Mayores aumentos de precio en el último mes con datos**")
approved_risers = data.risers(engine)
st.dataframe(risers_table(approved_risers), hide_index=True, use_container_width=True)

# --- 3. Qué pasaría si el lote se hubiera saltado el control ---------------------------
st.subheader("¿Qué mostraría el dashboard sin el control?")
st.write("Inyecta una corrupción controlada en el último lote aprobado y compara lo que el "
         "dashboard habría mostrado con lo que deja pasar el control.")
c1, c2 = st.columns([3, 1])
kinds = c1.multiselect("Corrupción a inyectar", sorted(KINDS), default=["typo_zeros"],
                       format_func=KIND_LABELS.get, key="whatif_kinds")
share = c2.slider("Filas afectadas (%)", 1, 20, 5, key="whatif_share")

bronze = data.last_approved_bronze(engine)
if not kinds:
    st.info("Elige al menos un tipo de corrupción.")
elif bronze is None:
    st.info("El último lote aprobado no está disponible.")
else:
    sim = simulate(bronze, kinds, fraction=share / 100)
    if not sim.report.passed:
        rules = ", ".join(sorted({d["rule"] for d in sim.report.failed_details}))
        st.error(f"⛔ RECHAZADO por el control de calidad: este lote nunca llegaría a silver "
                 f"ni a gold. Reglas que fallaron: {rules}")
    else:
        st.warning("⚠️ El control NO detectó esta corrupción (un punto ciego conocido). Estos "
                   "números habrían llegado al dashboard.")

    st.markdown("**Lo que habría mostrado el dashboard si el lote hubiera pasado**")
    ungated_series = sim.monthly[(sim.monthly["producto"] == product)
                                 & (sim.monthly["ciudad"] == city)]
    st.plotly_chart(price_figure(approved_series, ungated_series), use_container_width=True)

    approved_all = data.all_monthly(engine)[KEYS + ["precio_promedio"]]
    both = approved_all.merge(sim.monthly[KEYS + ["precio_promedio"]], on=KEYS, how="outer",
                              suffixes=("_ok", "_bad"))
    changed = int((~((both["precio_promedio_ok"] - both["precio_promedio_bad"]).abs() < 0.005)).sum())
    st.metric("Promedios mensuales que cambiaron por la corrupción", f"{changed} de {len(both)}")

    col_ok, col_bad = st.columns(2)
    col_ok.markdown("**Mayores aumentos: datos aprobados**")
    col_ok.dataframe(risers_table(approved_risers), hide_index=True, use_container_width=True)
    col_bad.markdown("**Mayores aumentos: sin el control**")
    col_bad.dataframe(risers_table(price_risers(sim.monthly)), hide_index=True,
                      use_container_width=True)
