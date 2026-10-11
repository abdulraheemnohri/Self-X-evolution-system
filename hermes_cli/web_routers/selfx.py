"""Local-first Self-X dashboard API.

These endpoints manage the durable goal/task journal only. They do not invoke a
model or execute task payloads. Any future executor must use Hermes' existing
scheduler, tool authorization and approval path.
"""
from __future__ import annotations

import json
from typing import Any, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from hermes_cli.web_deps import late

router = APIRouter()
get_hermes_home = late("get_hermes_home", "hermes_cli.config")
_resolve_profile_dir = late("_resolve_profile_dir", "hermes_cli.web_server_profiles")


def _store(profile: Optional[str] = None):
    from agent.selfx_goals import GoalStore

    if profile and profile.strip() and profile.strip().lower() not in {"current", "default"}:
        home = _resolve_profile_dir(profile.strip())
    else:
        home = Path(get_hermes_home())
    return GoalStore(Path(home) / "selfx" / "goals.sqlite3")


async def _read_object(request: Request) -> dict[str, Any]:
    """Parse a JSON object and return a client error for malformed/non-object bodies."""
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON body") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="JSON object required")
    return body


def _body_text(body: dict[str, Any], key: str, *, required: bool = False, limit: int = 500) -> str:
    value = body.get(key, "")
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail=f"{key} must be a string")
    value = value.strip()
    if required and not value:
        raise HTTPException(status_code=422, detail=f"{key} is required")
    if len(value) > limit:
        raise HTTPException(status_code=422, detail=f"{key} must be at most {limit} characters")
    return value


def _string_list(body: dict[str, Any], key: str, *, limit: int = 20, item_limit: int = 500) -> list[str]:
    value = body.get(key, [])
    if not isinstance(value, list) or len(value) > limit:
        raise HTTPException(status_code=422, detail=f"{key} must be a list of at most {limit} strings")
    result = []
    for item in value:
        if not isinstance(item, str) or len(item.strip()) > item_limit:
            raise HTTPException(status_code=422, detail=f"{key} items must be strings up to {item_limit} characters")
        item = item.strip()
        if item:
            result.append(item)
    return result


def _translate_store_error(exc: Exception):
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.get("/api/selfx/status")
async def selfx_status(profile: Optional[str] = Query(default=None)):
    store = _store(profile)
    goals = store.list_goals()
    tasks = store.list_tasks()
    goal_counts = {status: sum(1 for goal in goals if goal["status"] == status)
                   for status in ("active", "paused", "completed", "cancelled")}
    task_counts = {status: sum(1 for task in tasks if task["status"] == status)
                   for status in ("pending", "running", "completed", "failed", "cancelled")}
    return {
        "schema_version": 1,
        "execution_enabled": False,
        "goal_count": len(goals),
        "goal_status_counts": goal_counts,
        "task_count": len(tasks),
        "task_status_counts": task_counts,
        "goals": goals,
        "recent_tasks": sorted(tasks, key=lambda item: (item["updated_at"], item["id"]), reverse=True)[:10],
    }


@router.get("/api/selfx/identity")
async def selfx_identity():
    from agent.selfx_diagnostics import collect_identity
    return collect_identity()


@router.get("/api/selfx/diagnostics")
async def selfx_diagnostics(profile: Optional[str] = Query(default=None)):
    from agent.selfx_diagnostics import run_diagnostics
    home = Path(_resolve_profile_dir(profile.strip())) if profile and profile.strip() and profile.strip().lower() not in {"current", "default"} else Path(get_hermes_home())
    database = home / "selfx" / "goals.sqlite3"
    findings = run_diagnostics(paths=[home], database_paths=[database] if database.is_file() else [])
    return {"schema_version": 1, "read_only": True, "finding_count": len(findings),
            "findings": [finding.__dict__ for finding in findings]}


@router.get("/api/selfx/goals")
async def selfx_list_goals(status: Optional[str] = Query(default=None), profile: Optional[str] = Query(default=None)):
    try:
        return {"goals": _store(profile).list_goals(status=status)}
    except (KeyError, ValueError) as exc:
        _translate_store_error(exc)


@router.post("/api/selfx/goals")
async def selfx_create_goal(request: Request, profile: Optional[str] = Query(default=None)):
    body = await _read_object(request)
    try:
        return _store(profile).create_goal(
            _body_text(body, "title", required=True),
            description=_body_text(body, "description", limit=4000),
            success_criteria=_string_list(body, "success_criteria"),
        )
    except (KeyError, ValueError) as exc:
        _translate_store_error(exc)


@router.get("/api/selfx/goals/{goal_id}")
async def selfx_get_goal(goal_id: str, profile: Optional[str] = Query(default=None)):
    try:
        store = _store(profile)
        return {"goal": store.get_goal(goal_id), "progress": store.get_progress(goal_id),
                "milestones": store.list_milestones(goal_id=goal_id), "tasks": store.list_tasks(goal_id=goal_id)}
    except (KeyError, ValueError) as exc:
        _translate_store_error(exc)


@router.post("/api/selfx/goals/{goal_id}/status")
async def selfx_set_goal_status(goal_id: str, request: Request, profile: Optional[str] = Query(default=None)):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="JSON object required")
    status = _body_text(body, "status", required=True, limit=20)
    try:
        return _store(profile).set_goal_status(goal_id, status)
    except (KeyError, ValueError) as exc:
        _translate_store_error(exc)


@router.post("/api/selfx/goals/{goal_id}/milestones")
async def selfx_add_milestone(goal_id: str, request: Request, profile: Optional[str] = Query(default=None)):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="JSON object required")
    try:
        return _store(profile).add_milestone(
            goal_id, _body_text(body, "title", required=True),
            acceptance_criteria=_string_list(body, "acceptance_criteria"),
        )
    except (KeyError, ValueError) as exc:
        _translate_store_error(exc)


@router.get("/api/selfx/tasks")
async def selfx_list_tasks(goal_id: Optional[str] = Query(default=None), status: Optional[str] = Query(default=None),
                           profile: Optional[str] = Query(default=None)):
    try:
        return {"tasks": _store(profile).list_tasks(goal_id=goal_id, status=status)}
    except (KeyError, ValueError) as exc:
        _translate_store_error(exc)


@router.post("/api/selfx/goals/{goal_id}/tasks")
async def selfx_add_task(goal_id: str, request: Request, profile: Optional[str] = Query(default=None)):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="JSON object required")
    max_attempts = body.get("max_attempts", 3)
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 20:
        raise HTTPException(status_code=422, detail="max_attempts must be an integer from 1 to 20")
    payload = body.get("payload", {})
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="payload must be a JSON object")
    if len(json.dumps(payload, ensure_ascii=False)) > 16_384:
        raise HTTPException(status_code=422, detail="payload must not exceed 16 KiB")
    try:
        return _store(profile).add_task(
            goal_id, _body_text(body, "title", required=True),
            milestone_id=_body_text(body, "milestone_id", limit=100) or None,
            idempotency_key=_body_text(body, "idempotency_key", limit=200) or None,
            max_attempts=max_attempts,
            payload=payload,
        )
    except (KeyError, ValueError) as exc:
        _translate_store_error(exc)


@router.get("/api/selfx/goals/{goal_id}/progress")
async def selfx_goal_progress(goal_id: str, profile: Optional[str] = Query(default=None)):
    try:
        return _store(profile).get_progress(goal_id)
    except (KeyError, ValueError) as exc:
        _translate_store_error(exc)


@router.get("/api/selfx/tasks/{task_id}/history")
async def selfx_task_history(task_id: str, profile: Optional[str] = Query(default=None)):
    try:
        return {"events": _store(profile).list_task_events(task_id)}
    except (KeyError, ValueError) as exc:
        _translate_store_error(exc)


@router.post("/api/selfx/recovery/preview")
async def selfx_recovery_preview(profile: Optional[str] = Query(default=None)):
    store = _store(profile)
    running = store.list_tasks(status="running")
    return {"dry_run": True, "execution_enabled": False, "interrupted_task_count": len(running),
            "tasks": [{"task_id": task["id"], "attempts": task["attempts"],
                       "max_attempts": task["max_attempts"],
                       "next_status": "pending" if task["attempts"] < task["max_attempts"] else "failed"}
                      for task in running]}


@router.post("/api/selfx/recovery/apply")
async def selfx_recovery_apply(profile: Optional[str] = Query(default=None)):
    # Persist journal state only. This endpoint deliberately does not enqueue or execute tasks.
    return {"dry_run": False, "execution_enabled": False, "recovered": _store(profile).recover_interrupted_tasks(),
            "message": "Journal state updated only; tasks are not executed."}
