"""Behavioral tests for the read-only Self-X diagnostics primitives."""
from pathlib import Path

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
