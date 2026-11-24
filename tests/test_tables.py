import pandas as pd

from dashboard.tables import risers_table

COLUMNS = ["producto", "ciudad", "actual (COP)", "cambio"]


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
    assert list(risers_table(_risers()).columns) == COLUMNS


def test_values_use_the_spanish_decimal_comma_and_thousands_dot():
    table = risers_table(_risers())
    assert table["cambio"].tolist() == ["+54,3 %", "+21,2 %"]
    assert table["actual (COP)"].tolist() == ["20.157", "2.789"]


def test_negative_changes_keep_their_sign():
    df = _risers().assign(variacion_pct=[-25.0, 0.0])
    assert risers_table(df)["cambio"].tolist() == ["-25,0 %", "+0,0 %"]


def test_numbers_over_a_million_get_two_thousands_dots():
    df = _risers().assign(precio_promedio=[2210000.4, 1000.0])
    assert risers_table(df)["actual (COP)"].tolist() == ["2.210.000", "1.000"]


def test_empty_input_gives_an_empty_table_with_the_same_columns():
    empty = risers_table(pd.DataFrame(columns=["producto", "ciudad", "mes", "precio_anterior",
                                               "precio_promedio", "variacion_pct"]))
    assert empty.empty and list(empty.columns) == COLUMNS
