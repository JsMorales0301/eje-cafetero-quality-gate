"""Streamlit dashboard. Reads only the gold layer and the quality gate audit trail."""
import pandas as pd
import streamlit as st

from dashboard import data
from dashboard.charts import price_figure
from dashboard.tables import risers_table
from dashboard.whatif import price_risers, simulate
from pipeline.corruption import KINDS
from pipeline.db import get_engine

KEYS = ["producto", "ciudad", "mes"]

st.set_page_config(page_title="Eje Cafetero quality gate", layout="wide")
st.title("Eje Cafetero food prices: what a quality gate protects")
st.caption("Weekly wholesale prices from datos.gov.co (RAP Eje Cafetero). Every number in the "
           "first two sections comes from batches that passed the quality gate.")

engine = get_engine()
if not data.has_approved_data(engine):
    st.info("No approved data yet. Run `python -m pipeline.run` to load a batch.")
    st.stop()


# --- 1. Quality gate -------------------------------------------------------------------
st.subheader("Quality gate")
runs = data.quality_runs(engine)
passed = int(runs["passed"].sum())
a, b, c = st.columns(3)
a.metric("Last run", "✅ passed" if runs.loc[0, "passed"] else "⛔ rejected")
b.metric("Batches approved", passed)
c.metric("Batches rejected", len(runs) - passed)
shown_runs = runs.assign(result=runs["passed"].map({True: "✅ passed", False: "⛔ rejected"}))
st.dataframe(shown_runs[["executed_at", "batch_id", "result", "rows_checked", "failed_rules"]],
             hide_index=True, use_container_width=True)

# --- 2. Prices (gold) ------------------------------------------------------------------
st.subheader("Prices (gold layer)")
options = data.products_and_cities(engine)
left, right = st.columns(2)
product = left.selectbox("Product", sorted(options["producto"].unique()), key="product")
cities = sorted(options.loc[options["producto"] == product, "ciudad"])
city = right.selectbox("City", cities, key="city")
approved_series = data.price_series(engine, product, city)
st.plotly_chart(price_figure(approved_series), use_container_width=True)

st.markdown("**Biggest price increases in the latest month with data**")
approved_risers = data.risers(engine)
st.dataframe(risers_table(approved_risers), hide_index=True, use_container_width=True)

# --- 3. What if the batch had skipped the gate ----------------------------------------
st.subheader("What would the dashboard show without the gate?")
st.write("Inject a controlled corruption into the last approved batch and compare what the "
         "dashboard would have shown with what the gate lets through.")
c1, c2 = st.columns([3, 1])
kinds = c1.multiselect("Corruption to inject", sorted(KINDS), default=["typo_zeros"],
                       key="whatif_kinds")
share = c2.slider("Rows affected (%)", 1, 20, 5, key="whatif_share")

bronze = data.last_approved_bronze(engine)
if not kinds:
    st.info("Pick at least one kind of corruption.")
elif bronze is None:
    st.info("The last approved batch is not available.")
else:
    sim = simulate(bronze, kinds, fraction=share / 100)
    if not sim.report.passed:
        rules = ", ".join(sorted({d["rule"] for d in sim.report.failed_details}))
        st.error(f"⛔ REJECTED by the quality gate: this batch would never reach silver or "
                 f"gold. Rules failed: {rules}")
    else:
        st.warning("⚠️ The gate did NOT detect this corruption (a known blind spot). These "
                   "numbers would have reached the dashboard.")

    st.markdown("**What the dashboard would have shown, if it had been let through**")
    ungated_series = sim.monthly[(sim.monthly["producto"] == product)
                                 & (sim.monthly["ciudad"] == city)]
    st.plotly_chart(price_figure(approved_series, ungated_series), use_container_width=True)

    approved_all = data.all_monthly(engine)[KEYS + ["precio_promedio"]]
    both = approved_all.merge(sim.monthly[KEYS + ["precio_promedio"]], on=KEYS, how="outer",
                              suffixes=("_ok", "_bad"))
    changed = int((~((both["precio_promedio_ok"] - both["precio_promedio_bad"]).abs() < 0.005)).sum())
    st.metric("Monthly averages changed by the corruption", f"{changed} of {len(both)}")

    col_ok, col_bad = st.columns(2)
    col_ok.markdown("**Top increases: approved data**")
    col_ok.dataframe(risers_table(approved_risers), hide_index=True, use_container_width=True)
    col_bad.markdown("**Top increases: without the gate**")
    col_bad.dataframe(risers_table(price_risers(sim.monthly)), hide_index=True,
                      use_container_width=True)
