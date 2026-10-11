"""Tests for Self-X structured goals and restart-safe task journal."""
import pytest

from agent.selfx_goals import GoalStore


def test_goal_and_milestone_persist_with_measurable_criteria(tmp_path):
    path = tmp_path / "selfx.sqlite3"
    store = GoalStore(path)
    goal = store.create_goal("Improve diagnostics", success_criteria=["all tests pass"])
    milestone = store.add_milestone(goal["id"], "Add tests", acceptance_criteria=["unit tests"])
    reopened = GoalStore(path)
    assert reopened.get_goal(goal["id"])["success_criteria"] == ["all tests pass"]
    assert milestone["goal_id"] == goal["id"]
    assert milestone["acceptance_criteria"] == ["unit tests"]


def test_claim_is_single_start_and_completion_requires_running_task(tmp_path):
    store = GoalStore(tmp_path / "state.sqlite3")
    goal = store.create_goal("Goal")
    task = store.add_task(goal["id"], "Run verification", idempotency_key="verify-1")
    claimed = store.claim_task(task["id"])
    assert claimed["status"] == "running"
    assert claimed["attempts"] == 1
    assert store.claim_task(task["id"]) is None
    assert store.finish_task(task["id"])["status"] == "completed"
    with pytest.raises(ValueError):
        store.finish_task(task["id"])


def test_duplicate_idempotency_key_is_rejected(tmp_path):
    store = GoalStore(tmp_path / "state.sqlite3")
    goal = store.create_goal("Goal")
    store.add_task(goal["id"], "First", idempotency_key="same-key")
    with pytest.raises(Exception):
        store.add_task(goal["id"], "Duplicate", idempotency_key="same-key")


def test_restart_recovery_requeues_only_when_retry_budget_remains(tmp_path):
    store = GoalStore(tmp_path / "state.sqlite3")
    goal = store.create_goal("Goal")
    retryable = store.add_task(goal["id"], "Retryable", max_attempts=2)
    exhausted = store.add_task(goal["id"], "Exhausted", max_attempts=1)
    store.claim_task(retryable["id"])
    store.claim_task(exhausted["id"])
    recovered = store.recover_interrupted_tasks()
    by_id = {item["task_id"]: item["status"] for item in recovered}
    assert by_id == {retryable["id"]: "pending", exhausted["id"]: "failed"}
    assert store.claim_task(retryable["id"])["attempts"] == 2


def test_rejects_empty_titles_and_invalid_status(tmp_path):
    store = GoalStore(tmp_path / "state.sqlite3")
    with pytest.raises(ValueError):
        store.create_goal("  ")
    with pytest.raises(ValueError):
        store.set_goal_status("missing", "unknown")

def test_progress_projection_counts_tasks_and_milestones_without_claiming(tmp_path):
    store = GoalStore(tmp_path / "progress.sqlite3")
    goal = store.create_goal("Goal")
    store.add_milestone(goal["id"], "Milestone")
    completed = store.add_task(goal["id"], "Done")
    running = store.add_task(goal["id"], "In progress")
    store.claim_task(completed["id"])
    store.finish_task(completed["id"])
    store.claim_task(running["id"])

    progress = store.get_progress(goal["id"])
    assert progress["task_total"] == 2
    assert progress["task_counts"]["completed"] == 1
    assert progress["task_counts"]["running"] == 1
    assert progress["task_completion_ratio"] == 0.5
    assert progress["milestone_total"] == 1
    assert progress["milestone_counts"]["pending"] == 1
    assert store.list_tasks(goal_id=goal["id"], status="running")[0]["id"] == running["id"]


def test_task_and_milestone_queries_validate_filters(tmp_path):
    store = GoalStore(tmp_path / "queries.sqlite3")
    goal = store.create_goal("Goal")
    store.add_task(goal["id"], "Task")
    assert len(store.list_tasks(goal_id=goal["id"])) == 1
    assert store.list_tasks(status="completed") == []
    with pytest.raises(ValueError):
        store.list_tasks(status="unknown")
    with pytest.raises(KeyError):
        store.list_milestones(goal_id="missing")

