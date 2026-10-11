"""Local-first structured goals and restart-safe task journal for Self-X.

This module is intentionally storage-only: it does not execute tasks, call models,
or grant permissions. A caller must enforce its existing approval and tool policies.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


_GOAL_STATUSES = {"active", "paused", "completed", "cancelled"}
_TASK_STATUSES = {"pending", "running", "completed", "failed", "cancelled"}


class GoalStore:
    """SQLite-backed goals, measurable milestones, and idempotent task-run records."""

    def __init__(self, database: str | Path):
        self.database = Path(database).expanduser()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS selfx_goals (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    success_criteria TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL CHECK(status IN ('active','paused','completed','cancelled')),
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS selfx_milestones (
                    id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL REFERENCES selfx_goals(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    acceptance_criteria TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL CHECK(status IN ('pending','completed','cancelled')),
                    created_at REAL NOT NULL,
                    completed_at REAL
                );
                CREATE TABLE IF NOT EXISTS selfx_tasks (
                    id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL REFERENCES selfx_goals(id) ON DELETE CASCADE,
                    milestone_id TEXT REFERENCES selfx_milestones(id) ON DELETE SET NULL,
                    title TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL CHECK(status IN ('pending','running','completed','failed','cancelled')),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
                    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK(max_attempts >= 1),
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS selfx_tasks_status_idx ON selfx_tasks(status, created_at);
                CREATE INDEX IF NOT EXISTS selfx_milestones_goal_idx ON selfx_milestones(goal_id, status);
            """)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def create_goal(self, title: str, *, description: str = "",
                    success_criteria: list[str] | None = None) -> dict:
        title = title.strip()
        if not title:
            raise ValueError("Goal title must not be empty")
        now, goal_id = time.time(), str(uuid.uuid4())
        with self._connect() as db:
            db.execute(
                "INSERT INTO selfx_goals VALUES (?, ?, ?, ?, 'active', ?, ?)",
                (goal_id, title, description, self._json(success_criteria or []), now, now),
            )
        return self.get_goal(goal_id)

    def get_goal(self, goal_id: str) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT * FROM selfx_goals WHERE id = ?", (goal_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown goal: {goal_id}")
        result = dict(row)
        result["success_criteria"] = json.loads(result["success_criteria"])
        return result

    def list_goals(self, *, status: str | None = None) -> list[dict]:
        if status is not None and status not in _GOAL_STATUSES:
            raise ValueError(f"Unsupported goal status: {status}")
        with self._connect() as db:
            if status:
                rows = db.execute("SELECT * FROM selfx_goals WHERE status=? ORDER BY created_at", (status,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM selfx_goals ORDER BY created_at").fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["success_criteria"] = json.loads(item["success_criteria"])
            results.append(item)
        return results

    def set_goal_status(self, goal_id: str, status: str) -> dict:
        if status not in _GOAL_STATUSES:
            raise ValueError(f"Unsupported goal status: {status}")
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE selfx_goals SET status=?, updated_at=? WHERE id=?",
                (status, time.time(), goal_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown goal: {goal_id}")
        return self.get_goal(goal_id)

    def add_milestone(self, goal_id: str, title: str, *,
                      acceptance_criteria: list[str] | None = None) -> dict:
        title = title.strip()
        if not title:
            raise ValueError("Milestone title must not be empty")
        milestone_id, now = str(uuid.uuid4()), time.time()
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM selfx_goals WHERE id=?", (goal_id,)).fetchone():
                raise KeyError(f"Unknown goal: {goal_id}")
            db.execute(
                "INSERT INTO selfx_milestones VALUES (?, ?, ?, ?, 'pending', ?, NULL)",
                (milestone_id, goal_id, title, self._json(acceptance_criteria or []), now),
            )
            row = db.execute("SELECT * FROM selfx_milestones WHERE id=?", (milestone_id,)).fetchone()
        result = dict(row)
        result["acceptance_criteria"] = json.loads(result["acceptance_criteria"])
        return result

    def add_task(self, goal_id: str, title: str, *, milestone_id: str | None = None,
                 payload: dict | None = None, idempotency_key: str | None = None,
                 max_attempts: int = 3) -> dict:
        title = title.strip()
        if not title:
            raise ValueError("Task title must not be empty")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        task_id, now = str(uuid.uuid4()), time.time()
        key = idempotency_key or task_id
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM selfx_goals WHERE id=?", (goal_id,)).fetchone():
                raise KeyError(f"Unknown goal: {goal_id}")
            if milestone_id and not db.execute(
                "SELECT 1 FROM selfx_milestones WHERE id=? AND goal_id=?", (milestone_id, goal_id)
            ).fetchone():
                raise ValueError("Milestone does not belong to the specified goal")
            db.execute(
                """INSERT INTO selfx_tasks
                   (id,goal_id,milestone_id,title,idempotency_key,payload_json,status,attempts,max_attempts,last_error,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,'pending',0,?,'',?,?)""",
                (task_id, goal_id, milestone_id, title, key, self._json(payload or {}), max_attempts, now, now),
            )
            row = db.execute("SELECT * FROM selfx_tasks WHERE id=?", (task_id,)).fetchone()
        return self._task_dict(row)

    @staticmethod
    def _task_dict(row: sqlite3.Row) -> dict:
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def list_tasks(self, *, goal_id: str | None = None, status: str | None = None) -> list[dict]:
        """List task records for progress views; never claims or executes work."""
        if status is not None and status not in _TASK_STATUSES:
            raise ValueError(f"Unsupported task status: {status}")
        clauses, params = [], []
        if goal_id is not None:
            clauses.append("goal_id = ?")
            params.append(goal_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM selfx_tasks" + where + " ORDER BY created_at, id",
                params,
            ).fetchall()
        return [self._task_dict(row) for row in rows]

    def get_progress(self, goal_id: str) -> dict:
        """Return a stable, read-only progress projection for a single goal."""
        goal = self.get_goal(goal_id)
        tasks = self.list_tasks(goal_id=goal_id)
        milestones = self.list_milestones(goal_id=goal_id)
        task_counts = {status: 0 for status in sorted(_TASK_STATUSES)}
        for task in tasks:
            task_counts[task["status"]] += 1
        milestone_counts = {status: 0 for status in ("pending", "completed", "cancelled")}
        for milestone in milestones:
            milestone_counts[milestone["status"]] += 1
        total = len(tasks)
        return {
            "goal_id": goal_id,
            "goal_status": goal["status"],
            "task_total": total,
            "task_counts": task_counts,
            "task_completion_ratio": (task_counts["completed"] / total) if total else 0.0,
            "milestone_total": len(milestones),
            "milestone_counts": milestone_counts,
        }

    def list_milestones(self, *, goal_id: str) -> list[dict]:
        """List milestones for a goal in creation order."""
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM selfx_goals WHERE id=?", (goal_id,)).fetchone():
                raise KeyError(f"Unknown goal: {goal_id}")
            rows = db.execute(
                "SELECT * FROM selfx_milestones WHERE goal_id=? ORDER BY created_at, id",
                (goal_id,),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["acceptance_criteria"] = json.loads(item["acceptance_criteria"])
            results.append(item)
        return results

    def claim_task(self, task_id: str) -> dict | None:
        """Atomically claim a pending task once; repeated claims cannot double-start it."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM selfx_tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"Unknown task: {task_id}")
            if row["status"] != "pending" or row["attempts"] >= row["max_attempts"]:
                return None
            now = time.time()
            db.execute(
                "UPDATE selfx_tasks SET status='running', attempts=attempts+1, updated_at=? WHERE id=? AND status='pending'",
                (now, task_id),
            )
            updated = db.execute("SELECT * FROM selfx_tasks WHERE id=?", (task_id,)).fetchone()
        return self._task_dict(updated)

    def finish_task(self, task_id: str, *, error: str | None = None) -> dict:
        """Record task outcome. Errors are bounded and never interpreted as executable commands."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM selfx_tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"Unknown task: {task_id}")
            if row["status"] != "running":
                raise ValueError(f"Task must be running to finish (is {row['status']})")
            status = "failed" if error is not None else "completed"
            db.execute(
                "UPDATE selfx_tasks SET status=?, last_error=?, updated_at=? WHERE id=?",
                (status, str(error or "")[:2000], time.time(), task_id),
            )
            updated = db.execute("SELECT * FROM selfx_tasks WHERE id=?", (task_id,)).fetchone()
        return self._task_dict(updated)

    def recover_interrupted_tasks(self) -> list[dict]:
        """Requeue interrupted tasks with retry budget remaining; exhaust the rest as failed."""
        recovered_at = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            running = db.execute("SELECT * FROM selfx_tasks WHERE status='running'").fetchall()
            requeued, exhausted = [], []
            for row in running:
                if row["attempts"] < row["max_attempts"]:
                    db.execute(
                        "UPDATE selfx_tasks SET status='pending', last_error=?, updated_at=? WHERE id=? AND status='running'",
                        ("Recovered after interrupted process; retry requires normal policy checks.", recovered_at, row["id"]),
                    )
                    requeued.append(row["id"])
                else:
                    db.execute(
                        "UPDATE selfx_tasks SET status='failed', last_error=?, updated_at=? WHERE id=? AND status='running'",
                        ("Retry budget exhausted after interrupted process.", recovered_at, row["id"]),
                    )
                    exhausted.append(row["id"])
            return [
                {"task_id": task_id, "status": "pending", "reason": "interrupted_task_requeued"}
                for task_id in requeued
            ] + [
                {"task_id": task_id, "status": "failed", "reason": "retry_budget_exhausted"}
                for task_id in exhausted
            ]
