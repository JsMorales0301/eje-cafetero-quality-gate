"""Plotly figures. Colors are slots 1 and 2 of the validated categorical palette (light mode).
Text is Spanish; months are written by hand so no browser locale bundle is needed."""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd
import plotly.graph_objects as go

APPROVED_COLOR = "#2a78d6"   # slot 1, blue
UNGATED_COLOR = "#eb6834"    # slot 2, orange
APPROVED_NAME = "Aprobado por el control"
UNGATED_NAME = "Sin el control"
MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MAX_TICKS = 8
LABEL_GAP_PX = 10  # each label moves this far from the shared end point: 20 px apart


def _trace(df: pd.DataFrame, name: str, color: str) -> go.Scatter:
    return go.Scatter(
        x=df["mes"], y=df["precio_promedio"], name=name, mode="lines+markers",
        line={"color": color, "width": 2}, marker={"color": color, "size": 8},
        hovertemplate="%{y:,.0f} COP<extra>" + name + "</extra>",
    )


def _label(df: pd.DataFrame, name: str, yshift: int) -> dict:
    last = df.sort_values("mes").iloc[-1]
    return {"x": last["mes"], "y": last["precio_promedio"], "text": name, "showarrow": False,
            "xanchor": "left", "xshift": 10, "yshift": yshift}


def _labels(series: list) -> list:
    """Direct labels at each line's end; the higher line gets the upper label so they never
    overlap, even when both lines end at the same value."""
    ends = [df.sort_values("mes").iloc[-1]["precio_promedio"] for df, _, _ in series]
    order = sorted(range(len(series)), key=lambda i: ends[i])
    shifts = {i: (-LABEL_GAP_PX if rank == 0 else LABEL_GAP_PX)
              for rank, i in enumerate((order[0], order[-1]))}
    return [_label(df, name, shifts[i]) for i, (df, name, _) in enumerate(series)]


def _month_ticks(frames: list) -> tuple[list, list]:
    """A readable set of month ticks, labelled in Spanish ('ene 2024').

    Every month when there are few; otherwise January and July, or only January."""
    months = sorted({m for df in frames for m in df["mes"]})
    chosen = months
    if len(months) > MAX_TICKS:
        for modulus in (6, 12):
            chosen = [m for m in months if (m.month - 1) % modulus == 0]
            if len(chosen) <= MAX_TICKS:
                break
        if len(chosen) < 2:  # too few January ticks: thin the months themselves
            chosen = months[:: math.ceil(len(months) / MAX_TICKS)]
        elif len(chosen) > MAX_TICKS:  # more than ~8 years even with January only
            chosen = chosen[:: math.ceil(len(chosen) / MAX_TICKS)]
    return chosen, [f"{MONTHS_ES[m.month - 1]} {m.year}" for m in chosen]


def price_figure(approved: pd.DataFrame, ungated: Optional[pd.DataFrame] = None) -> go.Figure:
    """Monthly average price. One series needs no legend; two get a legend and direct labels."""
    series = [(approved, APPROVED_NAME, APPROVED_COLOR)]
    if ungated is not None and not ungated.empty:
        series.append((ungated, UNGATED_NAME, UNGATED_COLOR))

    fig = go.Figure([_trace(df, name, color) for df, name, color in series])
    if len(series) > 1:
        fig.update_layout(annotations=_labels(series))
    tick_values, tick_text = _month_ticks([df for df, _, _ in series])
    fig.update_layout(
        showlegend=len(series) > 1,
        legend={"orientation": "h", "y": 1.12},
        hovermode="x unified",
        separators=",.",  # decimal comma, thousands dot
        margin={"l": 10, "r": 150 if len(series) > 1 else 20, "t": 30, "b": 10},
        yaxis={"title": "Precio promedio (COP)", "gridcolor": "rgba(128,128,128,0.2)"},
        xaxis={"title": None, "tickmode": "array", "tickvals": tick_values,
               "ticktext": tick_text, "hoverformat": "%m/%Y"},
    )
    return fig
