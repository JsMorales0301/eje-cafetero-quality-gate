import pandas as pd

from dashboard.charts import APPROVED_COLOR, UNGATED_COLOR, price_figure

APPROVED, UNGATED = "Aprobado por el control", "Sin el control"


def _series(values, start="2024-01-01"):
    return pd.DataFrame({"mes": pd.date_range(start, periods=len(values), freq="MS"),
                         "precio_promedio": values})


def test_single_series_has_no_legend_and_uses_the_first_categorical_color():
    fig = price_figure(_series([100, 120]))
    assert len(fig.data) == 1
    assert fig.data[0].line.color == APPROVED_COLOR
    assert fig.layout.showlegend is False


def test_two_series_have_a_legend_and_distinct_validated_colors():
    fig = price_figure(_series([100, 120]), _series([1000, 1200]))
    assert [t.name for t in fig.data] == [APPROVED, UNGATED]
    assert fig.data[0].line.color == APPROVED_COLOR and fig.data[1].line.color == UNGATED_COLOR
    assert APPROVED_COLOR != UNGATED_COLOR
    assert fig.layout.showlegend is True


def test_lines_are_thin_with_visible_markers_and_a_value_hover():
    trace = price_figure(_series([100, 120])).data[0]
    assert trace.line.width == 2 and trace.marker.size >= 8
    assert "%{y" in trace.hovertemplate and "COP" in trace.hovertemplate


def test_direct_labels_never_overlap_even_when_series_end_at_the_same_value():
    fig = price_figure(_series([100, 120]), _series([100, 120]))
    first, second = fig.layout.annotations
    assert first.y == second.y            # same end point...
    assert first.yshift != second.yshift  # ...but the labels are pushed apart
    assert abs(first.yshift - second.yshift) >= 16


def test_higher_series_gets_the_upper_label():
    fig = price_figure(_series([100, 120]), _series([1000, 1200]))
    approved, ungated = fig.layout.annotations
    assert ungated.yshift > approved.yshift


def test_series_are_labelled_directly_at_their_last_point():
    fig = price_figure(_series([100, 120]), _series([1000, 1200]))
    assert [a.text for a in fig.layout.annotations] == [APPROVED, UNGATED]


def test_axis_and_numbers_follow_spanish_conventions():
    fig = price_figure(_series([100, 120]))
    assert fig.layout.yaxis.title.text == "Precio promedio (COP)"
    assert fig.layout.separators == ",."          # decimal comma, thousands dot
    assert fig.layout.xaxis.hoverformat == "%m/%Y"  # numeric: independent of the locale


def test_month_ticks_use_spanish_abbreviations():
    fig = price_figure(_series([100, 120]))
    assert list(fig.layout.xaxis.ticktext) == ["ene 2024", "feb 2024"]
    assert len(fig.layout.xaxis.tickvals) == len(fig.layout.xaxis.ticktext)


def test_a_long_series_gets_a_readable_number_of_ticks_including_every_spanish_month():
    fig = price_figure(_series(list(range(100, 140)), start="2022-01-01"))  # 40 months
    ticks = list(fig.layout.xaxis.ticktext)
    assert 3 <= len(ticks) <= 9
    assert ticks[0] == "ene 2022"
    months = {"ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"}
    assert {t.split()[0] for t in ticks} <= months
