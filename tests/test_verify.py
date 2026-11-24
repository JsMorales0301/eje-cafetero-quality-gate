"""`pipeline.verify`: the check that decides whether the example operation gave the expected
result. Pure comparison tests first, then runs against the real Postgres test database."""
import copy
import json

import pytest
from sqlalchemy import text

from pipeline.run import run_pipeline
from pipeline.verify import (EXIT_ERROR, EXIT_MISMATCH, EXIT_OK, EXPECTED_PATH, compare,
                             load_expected, main, verify_operation)

EXPECTED = {
    "rows": {"bronze_latest_batch": 30, "silver": 30, "gold_monthly": 24},
    "quality_gate_passed": True,
    "samples": [
        {"producto": "Patilla", "ciudad": "Pereira", "mes": "2024-03-01",
         "precio_promedio": "2090.00", "observaciones": 1},
    ],
}
ACTUAL = {
    "rows": {"bronze_latest_batch": 30, "silver": 30, "gold_monthly": 24},
    "gate_passed": True,
    "samples": [{"found": True, "precio_promedio": "2090.00", "observaciones": 1}],
}


def _actual(**changes):
    actual = copy.deepcopy(ACTUAL)
    for path, value in changes.items():
        node = actual
        *parents, leaf = path.split("__")
        for key in parents:
            node = node[int(key)] if key.isdigit() else node[key]
        node[int(leaf) if leaf.isdigit() else leaf] = value
    return actual


# --- the comparison itself (no database) -------------------------------------------------

def test_identical_results_have_no_problems():
    assert compare(EXPECTED, ACTUAL) == []


def test_a_wrong_row_count_names_the_layer_and_both_numbers():
    problems = compare(EXPECTED, _actual(rows__silver=0))
    assert problems == ["silver rows: expected 30, got 0"]


def test_a_missing_sample_row_is_reported_as_not_found():
    problems = compare(EXPECTED, _actual(samples__0__found=False))
    assert len(problems) == 1 and "Patilla" in problems[0] and "not found" in problems[0]


def test_a_wrong_price_shows_expected_and_actual_values():
    problems = compare(EXPECTED, _actual(samples__0__precio_promedio="20900.00"))
    assert len(problems) == 1
    assert "2090.00" in problems[0] and "20900.00" in problems[0]


def test_a_wrong_observation_count_is_reported():
    problems = compare(EXPECTED, _actual(samples__0__observaciones=2))
    assert len(problems) == 1 and "observaciones" in problems[0]


@pytest.mark.parametrize("gate, fragment", [(False, "rejected"), (None, "none recorded")])
def test_the_last_quality_gate_run_must_have_passed(gate, fragment):
    problems = compare(EXPECTED, _actual(gate_passed=gate))
    assert len(problems) == 1 and "quality gate" in problems[0] and fragment in problems[0]


def test_every_problem_is_reported_not_just_the_first():
    problems = compare(EXPECTED, _actual(rows__silver=0, rows__gold_monthly=1, gate_passed=False))
    assert len(problems) == 3


def test_numeric_prices_are_compared_by_value_not_by_text():
    assert compare(EXPECTED, _actual(samples__0__precio_promedio="2090.0")) == []


# --- the expected file ---------------------------------------------------------------------

def test_expected_file_is_valid_and_complete():
    expected = load_expected()
    assert EXPECTED_PATH.name == "expected_fixture.json"
    assert expected["rows"] == {"bronze_latest_batch": 30, "silver": 30, "gold_monthly": 24}
    assert expected["quality_gate_passed"] is True
    assert len(expected["samples"]) >= 3
    assert any(s["observaciones"] > 1 for s in expected["samples"])  # checks real averaging


# --- against the real database -------------------------------------------------------------

@pytest.fixture()
def clean_db(engine):
    def wipe():
        with engine.begin() as conn:
            conn.execute(text(
                "TRUNCATE bronze.precios_raw, silver.precios, gold.precio_mensual, "
                "gold.variacion_mensual, meta.quality_runs"))
    wipe()
    yield engine
    wipe()


def test_the_real_example_operation_gives_exactly_the_expected_result(clean_db):
    """This is what proves the expected file is right: it was computed from the sample
    independently of the SQL, and the real pipeline has to match it."""
    run_pipeline(clean_db, source="fixture")
    assert verify_operation(clean_db) == []


def test_an_empty_database_is_reported_without_crashing(clean_db):
    problems = verify_operation(clean_db)
    assert any("silver rows" in p for p in problems)
    assert any("none recorded" in p for p in problems)


def test_tampering_with_a_gold_price_is_detected(clean_db):
    run_pipeline(clean_db, source="fixture")
    with clean_db.begin() as conn:
        conn.execute(text("UPDATE gold.precio_mensual SET precio_promedio = 99999 "
                          "WHERE producto = 'Patilla'"))
    problems = verify_operation(clean_db)
    assert len(problems) == 1 and "Patilla" in problems[0] and "99999" in problems[0]


def test_a_rejected_batch_fails_verification_even_if_silver_still_holds_good_data(clean_db):
    run_pipeline(clean_db, source="fixture")
    run_pipeline(clean_db, source="fixture", corrupt=["duplicates"])  # gate rejects it
    problems = verify_operation(clean_db)
    assert any("quality gate" in p and "rejected" in p for p in problems)


# --- the command line ------------------------------------------------------------------------

def test_main_exit_codes_and_output(clean_db, monkeypatch, capsys):
    monkeypatch.setattr("pipeline.verify.get_engine", lambda: clean_db)

    run_pipeline(clean_db, source="fixture")
    assert main([]) == EXIT_OK
    assert "VERIFY OK" in capsys.readouterr().out

    with clean_db.begin() as conn:
        conn.execute(text("DELETE FROM silver.precios WHERE producto = 'Patilla'"))
    assert main([]) == EXIT_MISMATCH
    out = capsys.readouterr().out
    assert "VERIFY FAILED" in out and "silver rows: expected 30, got 29" in out


def test_main_reports_a_missing_expected_file_as_an_error_not_a_mismatch(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("pipeline.verify.EXPECTED_PATH", tmp_path / "nope.json")
    assert main([]) == EXIT_ERROR
    assert "VERIFY ERROR" in capsys.readouterr().out


def test_main_accepts_an_alternative_expected_file(clean_db, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("pipeline.verify.get_engine", lambda: clean_db)
    run_pipeline(clean_db, source="fixture")
    wrong = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    wrong["rows"]["gold_monthly"] = 1
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps(wrong), encoding="utf-8")
    assert main(["--expected", str(path)]) == EXIT_MISMATCH
    assert "gold_monthly rows: expected 1, got 24" in capsys.readouterr().out
