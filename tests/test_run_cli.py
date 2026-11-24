"""CLI contract of `pipeline.run.main` for failures that happen before any stage starts.

Exit code 1 must mean only "the quality gate rejected the batch"; misconfiguration is exit 2
and names its stage, so CI can tell a bad batch from a badly configured machine.
"""
from pipeline.run import EXIT_ERROR, main


def test_invalid_row_limit_is_a_config_error_not_a_gate_rejection(monkeypatch, capsys):
    monkeypatch.setenv("SOCRATA_ROW_LIMIT", "abc")
    code = main(["--source", "fixture"])
    out = capsys.readouterr().out
    assert code == EXIT_ERROR
    assert "STAGE config FAILED" in out and "SOCRATA_ROW_LIMIT" in out
    assert "RESULT FAILED stage=config exit=2" in out


def test_missing_database_configuration_is_a_config_error(monkeypatch, capsys):
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    code = main(["--source", "fixture"])
    out = capsys.readouterr().out
    assert code == EXIT_ERROR
    assert "missing environment variable POSTGRES_USER" in out
    assert "RESULT FAILED stage=config exit=2" in out
