import pandas as pd

from dashboard.charts import APPROVED_COLOR, UNGATED_COLOR, price_figure


def _series(values):
    return pd.DataFrame({"mes": pd.date_range("2024-01-01", periods=len(values), freq="MS"),
                         "precio_promedio": values})


def test_single_series_has_no_legend_and_uses_the_first_categorical_color():
    fig = price_figure(_series([100, 120]))
    assert len(fig.data) == 1
    assert fig.data[0].line.color == APPROVED_COLOR
    assert fig.layout.showlegend is False


def test_two_series_have_a_legend_and_distinct_validated_colors():
    fig = price_figure(_series([100, 120]), _series([1000, 1200]))
    assert [t.name for t in fig.data] == ["Approved by the gate", "Without the gate"]
    assert fig.data[0].line.color == APPROVED_COLOR and fig.data[1].line.color == UNGATED_COLOR
    assert APPROVED_COLOR != UNGATED_COLOR
    assert fig.layout.showlegend is True


def test_lines_are_thin_with_visible_markers_and_a_value_hover():
    trace = price_figure(_series([100, 120])).data[0]
    assert trace.line.width == 2 and trace.marker.size >= 8
    assert "%{y" in trace.hovertemplate


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
    labels = [a.text for a in fig.layout.annotations]
    assert labels == ["Approved by the gate", "Without the gate"]
