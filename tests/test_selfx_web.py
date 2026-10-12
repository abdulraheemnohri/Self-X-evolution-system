"""Focused tests for the Self-X dashboard journal API."""
import asyncio

import pytest
from fastapi import HTTPException

from agent.selfx_goals import GoalStore
from hermes_cli.web_routers import selfx as routes


class FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def run(coro):
    return asyncio.run(coro)


def test_dashboard_goal_task_and_history_round_trip(monkeypatch, tmp_path):
    store = GoalStore(tmp_path / "goals.sqlite3")
    monkeypatch.setattr(routes, "_store", lambda profile=None: store)

    goal = run(routes.selfx_create_goal(FakeRequest({
        "title": "Improve health checks",
        "description": "Keep diagnostics read-only",
        "success_criteria": ["No secret values emitted"],
    })))
    assert goal["title"] == "Improve health checks"
    assert goal["status"] == "active"

    task = run(routes.selfx_add_task(goal["id"], FakeRequest({
        "title": "Add API tests",
        "max_attempts": 2,
    })))
    assert task["status"] == "pending"
    assert task["max_attempts"] == 2

    status = run(routes.selfx_status())
    assert status["goal_count"] == 1
    assert status["task_count"] == 1
    assert status["execution_enabled"] is False

    detail = run(routes.selfx_get_goal(goal["id"]))
    assert detail["progress"]["task_total"] == 1
    assert detail["tasks"][0]["id"] == task["id"]

    history = run(routes.selfx_task_history(task["id"]))
    assert [event["event_type"] for event in history["events"]] == ["created"]


def test_dashboard_recovery_preview_does_not_mutate_and_apply_does_not_execute(monkeypatch, tmp_path):
    store = GoalStore(tmp_path / "goals.sqlite3")
    monkeypatch.setattr(routes, "_store", lambda profile=None: store)
    goal = store.create_goal("Recovery test")
    task = store.add_task(goal["id"], "Interrupted work")
    claimed = store.claim_task(task["id"])
    assert claimed["status"] == "running"

    preview = run(routes.selfx_recovery_preview())
    assert preview["dry_run"] is True
    assert preview["interrupted_task_count"] == 1
    assert store.list_tasks(status="running")

    result = run(routes.selfx_recovery_apply())
    assert result["execution_enabled"] is False
    assert result["recovered"][0]["task_id"] == task["id"]
    assert store.list_tasks(status="pending")
    assert [event["event_type"] for event in store.list_task_events(task["id"])] == ["created", "claimed", "recovered"]


def test_dashboard_rejects_invalid_payloads(monkeypatch, tmp_path):
    store = GoalStore(tmp_path / "goals.sqlite3")
    monkeypatch.setattr(routes, "_store", lambda profile=None: store)

    with pytest.raises(HTTPException) as exc:
        run(routes.selfx_create_goal(FakeRequest({"title": "  "})))
    assert exc.value.status_code == 422
    goal = store.create_goal("Input validation")
    with pytest.raises(HTTPException) as exc:
        run(routes.selfx_add_task(goal["id"], FakeRequest({"title": "Bad retries", "max_attempts": 0})))
    assert exc.value.status_code == 422
