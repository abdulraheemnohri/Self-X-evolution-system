# Self-X Evolution System

This document defines a safe, testable evolution layer for Hermes Agent. It is a design and implementation contract, not a claim that every module described here is already implemented.

## Goals and invariants

- Make capabilities and operational state inspectable.
- Diagnose failures and propose evidence-based repairs.
- Learn reusable procedures from successful work without trusting arbitrary internet content as instructions.
- Evaluate changes before promoting them.
- Preserve user control, auditability, portability, and rollback.
- Reuse Hermes configuration, memory, skills, scheduler, tool-policy, approval, and storage mechanisms.
- Never store API keys, tokens, passwords, or raw secrets in identity snapshots, reports, or audit records.
- Never allow self-learning to grant permissions, weaken policy, or bypass approval.
- No network access in local-only mode.
- Do not claim a repair succeeded until verification passes.


## Implemented foundation: structured goals and restart recovery

The initial local SQLite implementation lives in `agent/selfx_goals.py`.

- `GoalStore.create_goal/list_goals/get_goal/set_goal_status`: persist goals and explicit success criteria.
- `GoalStore.add_milestone`: attach acceptance criteria to a goal.
- `GoalStore.add_task`: create a durable task record with a unique idempotency key and bounded retry budget.
- `GoalStore.claim_task`: atomically claim a pending task so concurrent workers cannot both claim the same pending record.
- `GoalStore.finish_task`: record completion or a bounded error only for a running task.
- `GoalStore.recover_interrupted_tasks`: after a process restart, requeue running tasks only if retry budget remains; otherwise mark them failed.

This is a **task journal, not an autonomous executor**. Requeued work must pass the normal scheduler, approval, authorization, and tool-policy checks before it runs. Exactly-once execution of external side effects cannot be guaranteed by a SQLite status row alone; tasks that perform side effects must use idempotent operations or their own external idempotency keys. The module does not invoke shell commands, models, network services, or automatic repairs.

Targeted tests are in `tests/agent/test_selfx_goals.py`. They have been authored but must be run in a bootstrapped checkout before this feature is considered verified.

## 1. Self-Identity

**Purpose:** Maintain a read-only, timestamped inventory of capabilities and runtime configuration.

Responsibilities:
- Report app/runtime version, platform, enabled integrations, available tools, configured model/provider identifier, storage backend, and feature flags.
- Use capability states: available, disabled, misconfigured, unavailable, unknown.
- Distinguish configured capabilities from capabilities actually tested at runtime.
- Redact secrets and sensitive environment values.
- Record timestamp and source for each observation.

Suggested API: collect_identity, get_capability_status, export_identity.

Acceptance criteria:
- Collection is read-only and does not require an LLM call.
- Secret-like values are never emitted.
- Missing optional dependencies produce an explicit status rather than a crash.
- Unit tests cover capability states and redaction.

## 2. Self-Diagnostics

**Purpose:** Convert system observations into prioritized, actionable findings.

Checks:
- Runtime/dependency imports and version compatibility.
- Configuration schema and required values.
- Model/provider or local-runtime availability without exposing credentials.
- Disk space and writable-directory checks.
- Database integrity and migration state.
- Process/service health where supported.
- Recent errors, repeated tracebacks, and failed scheduled jobs.
- Skill metadata and declared dependency validation.

Each finding should include an ID, category, severity, summary, evidence, probable causes, suggested actions, timestamp, and whether a safe automatic fix may exist.

Acceptance criteria:
- Checks have timeouts and bounded output.
- Diagnostics do not mutate configuration or system state.
- Findings link to evidence and mark uncertainty.
- Unsupported platform checks are reported as skipped or unsupported.

## 3. Self-Repair

**Purpose:** Plan and verify narrowly scoped repairs using diagnostic evidence.

Lifecycle:
1. Create a repair proposal from a finding.
2. Classify risk as SAFE, MEDIUM, HIGH, or CRITICAL.
3. Describe affected resources, preconditions, expected outcome, and rollback.
4. Create a backup, snapshot, temporary worktree, or isolated workspace when applicable.
5. Require approval according to existing policy.
6. Execute the smallest viable change in a bounded subprocess or sandbox.
7. Run verification and relevant regression tests.
8. Record the result and restore the previous state if verification fails.

Initial automatic repairs should be narrow and reversible, such as rebuilding a disposable cache. Package upgrades, configuration changes, service restarts, permission changes, deletion, privileged commands, and network-exposure changes require policy-based approval.

Security requirements:
- Persist the plan before execution.
- Bind approval to an immutable plan digest; editing the plan invalidates approval.
- Use argument arrays rather than interpolated shell command strings.
- Enforce timeouts, output limits, workspace boundaries, and cancellation.
- Surface rollback failure as a critical finding.

## 4. Self-Research

**Purpose:** Gather evidence from configured sources and turn it into traceable knowledge or proposed work.

Sources may include official documentation, release notes, selected Git repositories/issues, user-provided URLs, and local project docs.

Pipeline:
1. Apply source allow/deny rules and network/local-only policy.
2. Fetch within request, size, time, and rate limits.
3. Treat fetched content as untrusted data, never as privileged instructions.
4. Extract claims with source URL, title, timestamp, and excerpt or content hash.
5. Deduplicate, detect contradictions, and label confidence.
6. Produce a report and optionally draft a goal, issue, or skill proposal.
7. Require review before installing dependencies, executing instructions, or modifying code.

Acceptance criteria:
- Externally sourced claims have provenance.
- Research cannot bypass tool permissions or approvals.
- No remote access occurs in local-only mode.
- Retrieved pages cannot directly trigger tool execution.
- Reports distinguish verified facts, disputed claims, and hypotheses.

## 5. Self-Evaluation

**Purpose:** Measure improvement instead of assuming it.

Evaluation suites:
- Task completion and correctness.
- Tool selection and argument validity.
- Memory retrieval quality.
- Research citation quality and contradiction handling.
- Skill success and regression rates.
- Repair verification and rollback correctness.
- Security-policy compliance and approval behavior.
- Latency, resource use, and cost where applicable.

Requirements:
- Use deterministic fixtures and synthetic CI tasks.
- Maintain versioned baselines and compare candidate revisions.
- Track pass rate, regressions, duration, and resource use.
- Do not use private user content for benchmarks without explicit opt-in.
- Security tests are hard gates; performance gains cannot offset critical safety regressions.

## 6. Self-Goals

**Purpose:** Convert approved objectives into trackable plans.

Goal records should include stable ID, title, description, source, priority, status, success criteria, risk, dependencies, optional due date, and timestamps. Store milestones and tasks with evidence, status, and retry budgets.

Lifecycle: PROPOSED → APPROVED → ACTIVE → BLOCKED/PAUSED → COMPLETED/ABANDONED.

Agent-suggested goals remain PROPOSED until accepted under configured policy. Active goals need measurable completion criteria and stop conditions. Scheduler integration must respect quiet hours, resource budgets, and pause/stop controls.

Acceptance criteria:
- Every active goal has a status and next action.
- Users can pause or cancel goals and stop running work.
- Repeated failures cause escalation or a blocked state, not infinite retries.
- Goals never grant new permissions.

## 7. Self-Skills

**Purpose:** Turn repeatable successful workflows into reusable, reviewable skills.

Lifecycle:
1. Observe a successful workflow and outcome.
2. Draft prerequisites, inputs, steps, expected outputs, limitations, and tests.
3. Scan for unsafe commands, secret exposure, suspicious instructions, and unbounded access.
4. Test in a disposable workspace with fixtures.
5. Compare against the stable skill.
6. Publish a versioned candidate and promote according to policy.
7. Track usage, failures, compatibility, and deprecation.

Skill metadata should include ID/version, provenance, supported platforms, prerequisites, permissions, risk category, tests, evaluation result, changelog, and rollback target.

Acceptance criteria:
- Learned content is data until validated as a skill.
- Skills cannot edit policy or read undeclared secrets.
- Failed revisions never overwrite the stable version.
- Skills are exportable and removable by the user.

## 8. Self-Recovery

**Purpose:** Resume interrupted work and restore known-good state without duplicating unsafe side effects.

Capabilities:
- Persist job transitions and checkpoints.
- Record completed steps, pending steps, idempotency keys, and external side effects.
- Recover interrupted tasks after restart.
- Detect stale locks and orphaned workers safely.
- Retry transient failures with bounded exponential backoff and a maximum retry count.
- Validate checkpoint schema and referenced artifacts before resuming.
- Restore skill/config/workspace snapshots when a verified rollback target exists.

Acceptance criteria:
- Recovery is idempotent and avoids repeating non-idempotent external actions.
- Ask for confirmation when an external side effect may already have occurred.
- Quarantine and report corrupt checkpoints.
- Recovery never disables policy controls or bypasses approval.

## Shared control plane

All modules must use existing Hermes authorization, approvals, tool policy, logging, and configuration. Do not create a parallel permission system.

Recommended shared services:
- SelfXRegistry: module discovery and versions.
- SelfXEventBus: typed, bounded, redacted events.
- SelfXStore: persistent state with schema versions and migrations.
- EvidenceStore: diagnostic evidence and research provenance with retention controls.
- ApprovalAdapter: approval bound to immutable action-plan digests.
- EvaluationRunner: deterministic checks in isolated workspaces.
- SnapshotManager: restorable checkpoints and rollback metadata.

Reuse the existing database abstraction and migrations. Do not add a second database or mandatory runtime dependency without architectural justification.

## UI and CLI surface

Add a Self-X section to the existing UI, reusing current patterns:
- Overview: health, identity summary, active goals, recent learning, pending approvals.
- Identity: capabilities, configuration status, redacted environment, platform support.
- Diagnostics: findings, evidence, severity filters, run/re-run controls.
- Repairs: plans, risk, diffs, approval status, logs, rollback.
- Research: sources, scheduled checks, evidence, reports, claim verification.
- Evaluations: suites, baselines, comparisons, regressions, promotion history.
- Goals: milestones, dependencies, budgets, pause/resume/cancel.
- Skills: drafts, validation, versions, tests, promotion, rollback.
- Recovery: checkpoints, interrupted jobs, retry status, restore actions.
- Settings: module toggles, schedules, retention, resource budgets, network policy, approval thresholds.

Suggested CLI commands (reconcile names with existing conventions before implementation):
- hermes self status
- hermes self identity
- hermes self diagnose --scope all
- hermes self repair plan FINDING_ID
- hermes self repair apply PLAN_ID
- hermes self repair rollback REPAIR_ID
- hermes self research TOPIC
- hermes self evaluate --suite NAME
- hermes self goals list|propose|pause|resume|cancel
- hermes self skills list|validate|evaluate|rollback
- hermes self recover --dry-run

## Storage and privacy

- Reuse existing database abstractions and migration conventions.
- Store structured records with schema versions and UTC timestamps.
- Apply retention limits to logs, fetched content, and evaluation artifacts.
- Redact secrets before logging or exporting.
- Provide user export/delete controls.
- Prefer metadata, short excerpts, and content hashes over storing full external pages.
- Respect workspace boundaries and platform-specific paths/permissions.

## Delivery phases

### Phase 0 — Repository audit
Map existing identity/config, doctor, logs, skills, memory, scheduler, policy, approval, storage, UI, and recovery mechanisms. Identify extension points before writing runtime code.

### Phase 1 — Read-only foundation
Implement Self-Identity and Self-Diagnostics with typed schemas, secret redaction, tests, and read-only CLI/UI views.

### Phase 2 — Durable orchestration
Implement Self-Goals and Self-Recovery using existing scheduler/job persistence, bounded retries, and idempotency.

### Phase 3 — Evaluation and skills
Implement benchmark baselines, versioned skill candidates, isolated tests, promotion gates, and rollback.

### Phase 4 — Research and repair
Implement source-governed research, evidence provenance, repair proposals, approvals, isolated execution, and verification.

### Phase 5 — UI and hardening
Integrate pages/settings; add cross-platform, security, failure-injection, migration, package-build, and regression tests.

## Required verification

- Unit tests for every module and schema.
- Integration tests for storage, policy, approval, scheduler, and skills.
- Failure-injection tests for interruption, corrupt checkpoints, failed repair, rollback failure, and duplicate external actions.
- Security tests for redaction, research prompt injection, path traversal, command injection, privilege escalation, and approval-plan tampering.
- Platform checks for every platform currently supported by this repository.
- Lint, type checks, package build, and normal non-live tests.
- Update documentation with exact commands and limitations.
- Report test results honestly; do not claim tests passed unless run.

## Definition of done

Each module has an implementation, tests, documented configuration, observable status, explicit permission boundaries, and a recovery path. Optional integrations degrade gracefully. Self-X never silently weakens Hermes security.


## Implementation status (current branch)

The first runtime slice now exists on `self-x-evolution-modules`:

- `agent/selfx_diagnostics.py` provides read-only runtime identity/capability snapshots and local dependency/path/free-space/SQLite quick-check diagnostics.
- `tests/agent/test_selfx_diagnostics.py` covers safe environment metadata, missing-path behavior, normal directory checks, and unavailable optional dependencies.
- This slice does not execute repairs, access the network, invoke a model, or change configuration.
- The functions are primitives only: CLI/UI routing, durable finding storage, provider/model resolution, and integration with existing Hermes doctor/policy services remain future work.
- Tests have been added but have not been executed in this editing environment. Run `scripts/run_tests.sh tests/agent/test_selfx_diagnostics.py` in a correctly bootstrapped development checkout.

### Goal/task progress query API

The goal journal exposes read-only query methods for dashboards and future CLI integration:

- `list_tasks(goal_id=None, status=None)` returns task records in stable creation order and validates status filters.
- `list_milestones(goal_id=...)` returns the selected goal's milestones and acceptance criteria.
- `get_progress(goal_id)` returns task/milestone counts and a completion ratio. An empty task list has ratio `0.0`; it is not treated as complete.
- These methods do not claim, schedule, execute, approve, or mutate work. Recovered/pending work must still pass the existing policy and approval pipeline.

Focused tests cover the progress projection, query filtering, and observational behavior. CI must pass before this slice is considered verified.

