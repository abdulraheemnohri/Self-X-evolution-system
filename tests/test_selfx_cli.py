"""Tests for the Self-X CLI parser and safe journal dispatch."""
import argparse
import json

from hermes_cli.subcommands import selfx


class FakeStore:
    def __init__(self):
        self.recovery_called = False

    def list_goals(self, status=None):
        return [{"id": "g1", "status": "active"}]

    def list_tasks(self, goal_id=None, status=None):
        if status == "running":
            return [{"id": "t1", "attempts": 1, "max_attempts": 3}]
        return []

    def recover_interrupted_tasks(self):
        self.recovery_called = True
        return [{"task_id": "t1", "status": "pending"}]

    def get_progress(self, goal_id):
        return {"goal_id": goal_id, "task_total": 0}

    def get_goal(self, goal_id):
        if goal_id == "missing":
            raise KeyError("Unknown goal: missing")
        return {"id": goal_id, "status": "active"}

    def list_milestones(self, *, goal_id):
        return []

    def list_task_events(self, task_id):
        return [{"task_id": task_id, "event_type": "created"}]


def parse_self(*argv):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    selfx.build_self_parser(subparsers, cmd_self=selfx.cmd_self)
    return parser.parse_args(["self", *argv])


def test_parser_exposes_goal_task_and_recovery_commands():
    args = parse_self("goals", "create", "Ship v1", "--success-criterion", "tests pass")
    assert args.self_action == "goal-create"
    assert args.title == "Ship v1"
    assert args.success_criteria == ["tests pass"]

    task = parse_self("tasks", "add", "goal-id", "Write tests", "--max-attempts", "2")
    assert task.self_action == "task-add"
    assert task.max_attempts == 2

    recovery = parse_self("recover")
    assert recovery.self_action == "recover"
    assert recovery.apply is False


def test_recovery_defaults_to_dry_run_and_does_not_mutate(monkeypatch, capsys):
    store = FakeStore()
    monkeypatch.setattr(selfx, "_store", lambda: store)
    args = parse_self("recover")
    assert selfx.cmd_self(args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is True
    assert output["tasks"][0]["next_status"] == "pending"
    assert store.recovery_called is False


def test_recovery_requires_explicit_apply(monkeypatch, capsys):
    store = FakeStore()
    monkeypatch.setattr(selfx, "_store", lambda: store)
    args = parse_self("recover", "--apply")
    assert selfx.cmd_self(args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is False
    assert store.recovery_called is True


def test_missing_goal_returns_nonzero_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(selfx, "_store", FakeStore)
    args = parse_self("goals", "show", "missing")
    assert selfx.cmd_self(args) == 2
    assert "Unknown goal" in capsys.readouterr().err


def test_identity_is_redacted_and_does_not_initialize_goal_database(monkeypatch, capsys):
    monkeypatch.setattr(selfx, "_store", lambda: (_ for _ in ()).throw(AssertionError("must stay read-only")))
    monkeypatch.setattr("agent.selfx_diagnostics.collect_identity", lambda: {
        "schema_version": 1, "secrets_included": False, "capabilities": []
    })
    args = parse_self("identity")
    assert selfx.cmd_self(args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["secrets_included"] is False


def test_diagnose_is_read_only_and_does_not_create_goal_database(monkeypatch, tmp_path, capsys):
    import hermes_cli.config as config

    seen = {}
    monkeypatch.setattr(selfx, "_store", lambda: (_ for _ in ()).throw(AssertionError("must stay read-only")))
    monkeypatch.setattr(config, "get_hermes_home", lambda: tmp_path)
    def fake_diagnostics(*, paths, database_paths):
        seen["paths"] = list(paths)
        seen["database_paths"] = list(database_paths)
        return []
    monkeypatch.setattr("agent.selfx_diagnostics.run_diagnostics", fake_diagnostics)
    args = parse_self("diagnose")
    assert selfx.cmd_self(args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["read_only"] is True
    assert output["finding_count"] == 0
    assert seen["paths"] == [tmp_path]
    assert seen["database_paths"] == []
    assert not (tmp_path / "selfx" / "goals.sqlite3").exists()
