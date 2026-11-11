# CAD Studio enterprise agent control plane — historical design

> Inherited upstream architecture notes. Implementation lists describe the source snapshot, including unfinished and overlapping items; they are not the ModelOps v0.1 capability contract. Current scope is in [README](../../README.md) and [SKILL](../../SKILL.md).

## Position and influences

The control plane was designed to turn graphical configuration into auditable, reusable, replayable mechanical-engineering jobs:

```text
Graphical configuration -> Enterprise job contract -> Codex execution -> Skill/toolchain -> Review gate -> Delivery feedback
```

Codex remained the executor and `solidworks-automation` the underlying skill. From `datawhalechina/hello-agents`, the design adopted roles, tools, memory, context, protocols, evaluation, reusable workflows, and case-driven integration. Hermes Agent informed long-running workers, separate Agent Profile/Skill/Memory layers, delegation/review, gateways, audit, permissions, and recoverable execution. The intended scope was CAD/Skills rather than a general-purpose framework.

## Module boundaries

| Module | Responsibility |
| --- | --- |
| UI | Configuration, queues, prompt previews, and results |
| Queue | JSON persistence and offline recovery |
| Agent Contract | Compile Agent Profile, Policy, Prompt, and Output Schema |
| Worker | Dispatch mock / Codex / CAD handlers |
| Codex Executor | Invoke `codex exec`, reference the skill, and produce structured output |
| Reviewer Gate | Check actual holes, GB/T drawings, tests, Git state, and artifacts |
| Artifact Store | Retain agent output, CAD, reviews, and queue logs |

## Historical implementation record

The recorded implementation list included a Tauri local queue, Python worker, `executor: "codex"` bridge and UI, Agent Profile/prompt compiler, final-response JSON schema, versioned job schema, default `workspace-write` sandbox, workspace allowlist, and fixed output directory.

Queue safeguards included claim locks, leases, stale-running recovery, bad-job quarantine, heartbeat renewal, cancellation, JSONL events, and saved stdout/stderr. Policy approval covered Git push, full-access sandbox, CAD macros, external network, cross-workspace writes, and deletion; changed approval reasons required reapproval.

Artifact Ledger recorded successful-task paths, existence, size, and SHA-256. Worker Control was listed as able to start/stop a local Python worker and show status/PID; Worker Health recorded heartbeat, queue counts, recoveries, and recent errors. Reviewer Gate performed artifact and lightweight STEP/STL/DXF/PDF/DWG checks.

The original outstanding list still included in-app worker start/stop and real-time queue logs, despite overlap with the implementation list. Treat that as an unresolved historical snapshot rather than verified current functionality. Other outstanding work included multi-agent scheduling/review, memory and enterprise permissions, production-grade native CAD rollback, HMAC signatures, and an immutable audit ledger.

## Minimum operating principles

- Use structured JSON jobs, output files, explicit skill paths for Codex calls, and validation records for deliveries.
- Manufacturing artifacts must pass Reviewer Gate.
- Unspecified engineering choices use `auto_best`, with rationale and residual risks recorded.
- Enable Codex execution explicitly; never execute it silently by default.
- `danger-full-access` requires both task approval and worker `--codex-full-access`; it is not a default.
- Frontend job JSON is untrusted; enforce policy in the worker/control plane.

These are historical upstream policies; current host instructions and user authorization still govern task execution.

## Policy Gate

Before `codex exec`, check:

- `policy.approval == "manual-required"`.
- `policy.requirePush == true` or UI `commitAndPush == true`.
- `policy.sandbox == "danger-full-access"`.
- Requested `capabilities`: `git_push`, `full_access`, `cad_macro`, `external_network`, `cross_workspace`, `delete_files`.

Matches move the job to `approval_required`, populate `approvalReasons`, and emit `policy.approval_required`. Approval records `approvedAt`, `approvedBy`, and `approvedPolicyReasons`, then requeues the job as `queued`. Recompute reasons before execution and proceed only when they still match the approved set.

## Artifact Ledger

Aggregate `result.outputPath`, `result.outputs`, `result.artifacts`, and job-level `artifacts` into `queue/ledgers/{job_id}.ledger.json`. Record kind/path, existence/directory status, size/SHA-256, result messages, and verification summaries. The ledger records facts; it does not certify manufacturing acceptance. Native handlers must verify P0 STEP/STL/DWG/PDF files exist, open, and meet manufacturing requirements before `passed`.

## Worker Health and Reviewer Gate

`queue/worker_health.json` records heartbeat, PID, queue counts, processed jobs, stale-running recoveries, and recent errors. Process liveness and queue health are separate: failed or waiting-approval jobs must remain visible.

Reviewer reports at `queue/reviews/{job_id}.review.json` check declared artifacts, existence, nonempty content, SHA-256, and headers/structural markers for STEP/STP, STL, DXF, PDF, and DWG. Proprietary SLDPRT was warning-only in this snapshot; native SolidWorks opening remained planned.

## Historical next steps

1. Queue event timeline, running retry policy, and health display.
2. Native SolidWorks/AutoCAD reopen checks, drawing chains, and actual 3D-print hole review.
3. Persist crash reasons and add health scoring/timeline.
4. Show execution plans, gates, and impact scope; keep raw prompts in advanced details.
5. Add Planner/Executor/Reviewer stages, prioritizing traceability and acceptance over process count.
