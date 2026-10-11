"""CLI for inspecting and managing the local Self-X goal/task journal.

The journal stores plans and task state only. It never executes task payloads,
invokes a model, or bypasses Hermes authorization/approval controls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _store():
    from hermes_cli.config import get_hermes_home
    from agent.selfx_goals import GoalStore

    return GoalStore(Path(get_hermes_home()) / "selfx" / "goals.sqlite3")


def _emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def build_self_parser(subparsers, *, cmd_self) -> None:
    """Attach the self command and its explicit, local-only management commands."""
    parser = subparsers.add_parser(
        "self",
        help="Inspect and manage the local Self-X evolution journal",
        description=(
            "Local Self-X goal/task journal controls. Task records are not executed "
            "by these commands; normal scheduler, policy and approval gates remain mandatory."
        ),
    )
    actions = parser.add_subparsers(dest="self_command")

    status = actions.add_parser("status", help="Summarize local goals and tasks")
    status.set_defaults(self_action="status")

    identity = actions.add_parser("identity", help="Show a redacted runtime/capability snapshot")
    identity.set_defaults(self_action="identity")
    diagnose = actions.add_parser("diagnose", help="Run read-only local health checks")
    diagnose.set_defaults(self_action="diagnose")

    goals = actions.add_parser("goals", help="Create, list, inspect or change goal status")
    goal_actions = goals.add_subparsers(dest="self_goal_action", required=True)
    create = goal_actions.add_parser("create", help="Create a local goal")
    create.add_argument("title")
    create.add_argument("--description", default="")
    create.add_argument("--success-criterion", action="append", default=[], dest="success_criteria")
    create.set_defaults(self_action="goal-create")
    listing = goal_actions.add_parser("list", help="List goals")
    listing.add_argument("--status", choices=("active", "paused", "completed", "cancelled"))
    listing.set_defaults(self_action="goal-list")
    show = goal_actions.add_parser("show", help="Show a goal and its progress")
    show.add_argument("goal_id")
    show.set_defaults(self_action="goal-show")
    for action in ("pause", "resume", "cancel", "complete"):
        change = goal_actions.add_parser(action, help=f"{action.capitalize()} a goal")
        change.add_argument("goal_id")
        change.set_defaults(self_action=f"goal-{action}")

    milestones = actions.add_parser("milestones", help="Manage goal milestones")
    milestone_actions = milestones.add_subparsers(dest="self_milestone_action", required=True)
    milestone_add = milestone_actions.add_parser("add", help="Add a milestone")
    milestone_add.add_argument("goal_id")
    milestone_add.add_argument("title")
    milestone_add.add_argument("--criterion", action="append", default=[], dest="criteria")
    milestone_add.set_defaults(self_action="milestone-add")
    milestone_list = milestone_actions.add_parser("list", help="List milestones for a goal")
    milestone_list.add_argument("goal_id")
    milestone_list.set_defaults(self_action="milestone-list")

    tasks = actions.add_parser("tasks", help="Inspect and record tasks")
    task_actions = tasks.add_subparsers(dest="self_task_action", required=True)
    task_add = task_actions.add_parser("add", help="Record a task (does not execute it)")
    task_add.add_argument("goal_id")
    task_add.add_argument("title")
    task_add.add_argument("--milestone-id")
    task_add.add_argument("--idempotency-key")
    task_add.add_argument("--max-attempts", type=int, default=3)
    task_add.set_defaults(self_action="task-add")
    task_list = task_actions.add_parser("list", help="List task records")
    task_list.add_argument("--goal-id")
    task_list.add_argument("--status", choices=("pending", "running", "completed", "failed", "cancelled"))
    task_list.set_defaults(self_action="task-list")
    progress = task_actions.add_parser("progress", help="Show task/milestone progress for a goal")
    progress.add_argument("goal_id")
    progress.set_defaults(self_action="task-progress")
    history = task_actions.add_parser("history", help="Show lifecycle events for a task")
    history.add_argument("task_id")
    history.set_defaults(self_action="task-history")

    recover = actions.add_parser("recover", help="Inspect or requeue interrupted task records")
    recover.add_argument(
        "--apply", action="store_true",
        help="Persist recovery transitions; this does not execute requeued tasks",
    )
    recover.set_defaults(self_action="recover")

    parser.set_defaults(func=cmd_self)


def cmd_self(args) -> int:
    """Dispatch Self-X journal commands with machine-readable JSON output."""
    action = getattr(args, "self_action", None) or "status"
    try:
        # Identity and diagnostics must remain read-only and must not initialize the goal DB.
        store = None if action in {"identity", "diagnose"} else _store()
        if action == "identity":
            from agent.selfx_diagnostics import collect_identity
            _emit(collect_identity())
        elif action == "diagnose":
            from agent.selfx_diagnostics import run_diagnostics
            from hermes_cli.config import get_hermes_home
            home = Path(get_hermes_home())
            database = home / "selfx" / "goals.sqlite3"
            findings = run_diagnostics(
                paths=[home],
                database_paths=[database] if database.is_file() else [],
            )
            _emit({
                "schema_version": 1,
                "read_only": True,
                "finding_count": len(findings),
                "findings": [finding.__dict__ for finding in findings],
            })
        elif action == "status":
            goals = store.list_goals()
            tasks = store.list_tasks()
            counts = {key: 0 for key in ("pending", "running", "completed", "failed", "cancelled")}
            for task in tasks:
                counts[task["status"]] = counts.get(task["status"], 0) + 1
            _emit({
                "schema_version": 1,
                "storage": "local-sqlite",
                "execution_enabled": False,
                "goal_count": len(goals),
                "goal_status_counts": {
                    key: sum(1 for goal in goals if goal["status"] == key)
                    for key in ("active", "paused", "completed", "cancelled")
                },
                "task_count": len(tasks),
                "task_status_counts": counts,
            })
        elif action == "goal-create":
            _emit(store.create_goal(
                args.title, description=args.description,
                success_criteria=args.success_criteria,
            ))
        elif action == "goal-list":
            _emit(store.list_goals(status=args.status))
        elif action == "goal-show":
            _emit({
                "goal": store.get_goal(args.goal_id),
                "progress": store.get_progress(args.goal_id),
                "milestones": store.list_milestones(goal_id=args.goal_id),
                "tasks": store.list_tasks(goal_id=args.goal_id),
            })
        elif action in {"goal-pause", "goal-resume", "goal-cancel", "goal-complete"}:
            status = {
                "goal-pause": "paused", "goal-resume": "active",
                "goal-cancel": "cancelled", "goal-complete": "completed",
            }[action]
            _emit(store.set_goal_status(args.goal_id, status))
        elif action == "milestone-add":
            _emit(store.add_milestone(args.goal_id, args.title, acceptance_criteria=args.criteria))
        elif action == "milestone-list":
            _emit(store.list_milestones(goal_id=args.goal_id))
        elif action == "task-add":
            _emit(store.add_task(
                args.goal_id, args.title, milestone_id=args.milestone_id,
                idempotency_key=args.idempotency_key, max_attempts=args.max_attempts,
            ))
        elif action == "task-list":
            _emit(store.list_tasks(goal_id=args.goal_id, status=args.status))
        elif action == "task-progress":
            _emit(store.get_progress(args.goal_id))
        elif action == "task-history":
            _emit(store.list_task_events(args.task_id))
        elif action == "recover":
            running = store.list_tasks(status="running")
            if not args.apply:
                _emit({
                    "dry_run": True,
                    "interrupted_task_count": len(running),
                    "tasks": [
                        {"task_id": task["id"], "attempts": task["attempts"],
                         "max_attempts": task["max_attempts"],
                         "next_status": "pending" if task["attempts"] < task["max_attempts"] else "failed"}
                        for task in running
                    ],
                    "message": "No state changed. Pass --apply to persist recovery; tasks will not be executed.",
                })
            else:
                _emit({
                    "dry_run": False,
                    "recovered": store.recover_interrupted_tasks(),
                    "message": "State updated only; normal scheduler/policy/approval checks still apply.",
                })
        else:
            print(f"Unsupported Self-X action: {action}", file=sys.stderr)
            return 2
    except (KeyError, ValueError) as exc:
        print(f"Self-X error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Self-X could not complete the request: {exc}", file=sys.stderr)
        return 1
    return 0
