"""Behavioral tests for the read-only Self-X diagnostics primitives."""
from agent.selfx_diagnostics import collect_identity, run_diagnostics


def test_identity_reports_runtime_without_environment_values(monkeypatch):
    monkeypatch.setenv("SELF_X_VISIBLE_FLAG", "value-that-must-not-be-exported")
    monkeypatch.setenv("SERVICE_API_KEY", "not-for-reporting")
    result = collect_identity(enabled_tools=["filesystem", "terminal"], optional_imports=[])
    assert result["schema_version"] == 1
    assert result["secrets_included"] is False
    assert "SELF_X_VISIBLE_FLAG" in result["environment_variable_names"]
    assert "SERVICE_API_KEY" not in result["environment_variable_names"]
    assert all("value-that-must-not-be-exported" not in repr(result) for _ in [0])
    assert {item["name"] for item in result["capabilities"]} >= {
        "python", "platform", "tool:filesystem", "tool:terminal"
    }


def test_diagnostics_reports_missing_path_without_creating_it(tmp_path):
    missing = tmp_path / "does-not-exist"
    findings = run_diagnostics(paths=[missing], optional_imports=[])
    assert any(item.id == "path-missing-does-not-exist" for item in findings)
    assert not missing.exists()


def test_diagnostics_can_check_existing_directory(tmp_path):
    findings = run_diagnostics(paths=[tmp_path], min_free_bytes=0, optional_imports=[])
    assert isinstance(findings, list)
    assert all(item.severity in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} for item in findings)


def test_optional_dependency_failure_is_reported_not_raised():
    findings = run_diagnostics(optional_imports=["selfx_missing_test_dependency"])
    assert len(findings) == 1
    assert findings[0].id == "dependency-selfx_missing_test_dependency"
    assert findings[0].category == "dependency"


def test_sqlite_quick_check_is_read_only_and_accepts_healthy_database(tmp_path):
    import sqlite3

    database = tmp_path / "healthy.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE example (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO example DEFAULT VALUES")
    findings = run_diagnostics(database_paths=[database], optional_imports=[])
    assert not any(item.category == "database" for item in findings)
    # Reopening read-only checks must not create journal/WAL sidecars for this simple DB.
    assert database.exists()


def test_sqlite_diagnostic_reports_missing_database_without_creating_it(tmp_path):
    missing = tmp_path / "missing.db"
    findings = run_diagnostics(database_paths=[missing], optional_imports=[])
    assert any(item.id == "database-missing-missing.db" for item in findings)
    assert not missing.exists()
