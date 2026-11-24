import pandas as pd

from dashboard.tables import risers_table


def _risers():
    return pd.DataFrame({
        "producto": ["Pitahaya", "Piña gold"],
        "ciudad": ["Pereira", "Pereira"],
        "mes": pd.to_datetime(["2025-09-01"] * 2),
        "precio_anterior": [13066.6, 2301.8],
        "precio_promedio": [20156.6, 2789.4],
        "variacion_pct": [54.26, 21.19],
    })


def test_table_is_narrow_enough_for_two_side_by_side():
    table = risers_table(_risers())
    assert list(table.columns) == ["product", "city", "current (COP)", "change"]


def test_values_are_formatted_for_reading():
    table = risers_table(_risers())
    assert table["change"].tolist() == ["+54.3%", "+21.2%"]
    assert table["current (COP)"].tolist() == ["20,157", "2,789"]


def test_negative_changes_keep_their_sign():
    df = _risers().assign(variacion_pct=[-25.0, 0.0])
    assert risers_table(df)["change"].tolist() == ["-25.0%", "+0.0%"]


def test_empty_input_gives_an_empty_table_with_the_same_columns():
    empty = risers_table(pd.DataFrame(columns=["producto", "ciudad", "mes", "precio_anterior",
                                               "precio_promedio", "variacion_pct"]))
    assert empty.empty and list(empty.columns) == ["product", "city", "current (COP)", "change"]
