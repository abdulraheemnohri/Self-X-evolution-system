# Self-X Evolution Agent

**Self-X is a self-hosted AI agent and controlled self-evolution system.** It provides a standalone `self-x` command, its own local data directory, and a safety-focused evolution layer for identity, diagnostics, goals, task history, recovery, and future verified repair/research/evaluation/skill workflows.

This repository evolves a mature Hermes-compatible agent runtime. The existing runtime internals are retained as a compatibility layer while Self-X becomes the product-facing interface; this is not a claim that every internal module has already been renamed. New installs should use `self-x`, not `hermes`.

## Principles

- **Local-first:** Self-X keeps its own user data under `~/.selfx` on Linux/macOS, or `%LOCALAPPDATA%\Self-X` on Windows by default.
- **User-controlled autonomy:** plans and journal entries do not execute themselves; existing scheduler, authorization, tool-policy, and approval gates remain in force.
- **Auditable state:** goals, milestones, task progress, and lifecycle events are stored in local SQLite.
- **Recovery with limits:** interrupted task records can be inspected before recovery; recovery does not promise exactly-once external side effects.
- **Read-only health checks:** identity and diagnostic collection must not run repairs or reveal secret values.
- **Compatibility during migration:** `hermes` remains a legacy command for internal tools and existing workflows. Self-X is the new public entry point.

## Install

### Linux, macOS, or WSL

Review the installer before running it. It checks out this repository and prepares the agent runtime.

```bash
curl -fsSL https://raw.githubusercontent.com/abdulraheemnohri/Self-X-evolution-system/main/scripts/install.sh -o self-x-install.sh
less self-x-install.sh
bash self-x-install.sh
```

### Windows PowerShell

Review the script, then run it from a PowerShell session:

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/abdulraheemnohri/Self-X-evolution-system/main/scripts/install.ps1 -OutFile self-x-install.ps1
Get-Content .\self-x-install.ps1
.\self-x-install.ps1
```

The source installer defaults to this repository and a Self-X-specific data directory. Existing deployments can explicitly set `SELF_X_HOME` and `SELF_X_REPO_URL`. Legacy `HERMES_HOME` and `HERMES_REPO_URL` variables are still accepted for compatibility.

> These URLs target `main`. Changes in an open pull request are not available through the installer until they are merged.

## Quick start

```bash
self-x --help
self-x doctor
self-x self status
self-x self identity
self-x self diagnose
```

If you installed the project in editable/development mode, refresh the environment after pulling changes so the `self-x` console script is registered.

## Self-X goal and task journal

The journal is a local planning and tracking layer. It is **not** a task executor.

```bash
self-x self goals create "Improve diagnostics" \
  --success-criterion "Regression tests pass"
self-x self goals list
self-x self goals show GOAL_ID
self-x self goals pause GOAL_ID
self-x self goals resume GOAL_ID

self-x self milestones add GOAL_ID "CLI integration" \
  --criterion "Commands have tests"
self-x self tasks add GOAL_ID "Run regression tests" --max-attempts 2
self-x self tasks list --goal-id GOAL_ID
self-x self tasks progress GOAL_ID
self-x self tasks history TASK_ID

# Preview recovery first; no state changes:
self-x self recover
# Explicitly persist recovery transitions (still does not execute tasks):
self-x self recover --apply
```

## Self-X evolution modules

| Module | Current boundary |
|---|---|
| Self-Identity | Read-only runtime/capability snapshot; secret values are not emitted. |
| Self-Diagnostics | Read-only dependency, path, disk-space, and SQLite checks. |
| Self-Goals | SQLite goal, milestone, and task records with status controls. |
| Task History | Lifecycle events for task creation, claims, outcomes, and recovery. |
| Self-Recovery | Dry-run preview by default; explicit apply requeues eligible records or marks exhausted records failed. |
| Self-Repair | Design target: isolated, reversible repair proposals with verification and approval. Not an unrestricted auto-fixer. |
| Self-Research | Design target: source-attributed evidence; retrieved content remains untrusted data. |
| Self-Evaluation | Design target: versioned benchmarks and security regression gates. |
| Self-Skills | Design target: reviewed, tested, versioned procedures; learned content cannot grant permissions. |

The design document at [`docs/self-x-evolution-system.md`](docs/self-x-evolution-system.md) distinguishes implemented code from planned modules. Do not treat a design description as proof that a feature is complete.

## Development and tests

Use the repository's supported development bootstrap, then run the focused tests:

```bash
pytest -q tests/test_selfx_cli.py tests/agent/test_selfx_goals.py tests/agent/test_selfx_diagnostics.py
```

The project includes a broad existing runtime and platform-specific build checks; run the full CI suite before merging or distributing a release. No test result should be assumed from adding a test file alone.

## Security model

- Research results, webpages, and generated skill content are untrusted inputs.
- Identity reports and diagnostic findings must not include tokens, passwords, or secret values.
- Goal/task records do not grant tool permissions.
- Recovered work must pass the existing scheduler, authorization, tool-policy, and approval checks before any executor can run it.
- Package upgrades, configuration edits, service changes, deletion, privileged commands, and other high-risk repairs require policy-based approval and a rollback plan.
- Local-only mode must not make remote requests.

## Upstream and license

Self-X is a derivative project that retains portions of the Hermes-compatible runtime while the migration proceeds. Preserve upstream license and attribution notices in the repository. See [LICENSE](LICENSE) for the applicable license terms.
