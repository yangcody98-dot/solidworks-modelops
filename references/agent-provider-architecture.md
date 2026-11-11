# Multiple agent provider architecture

## Goal

CAD Studio supports different user environments without binding to one model or CLI. All providers share the CAD task protocol, approval policy, knowledge retrieval, artifact ledger, and review gates. Provider-specific behavior stays in command compilation and result parsing.

```text
User task
  -> UnifiedAutomationJob
  -> Policy Gate
  -> Provider Adapter
  -> Codex / Claude Code / Gemini CLI / OpenCode
  -> UnifiedAgentResult
  -> Artifact Ledger
  -> CAD/B-Rep/Motion Reviewer Gate
  -> Local delivery directory
```

## Keep provider states distinct

The interface and logs must distinguish these states:

| State | Evidence | May it be described as connected? |
|---|---|---|
| Not installed | CLI entry point missing or `--version` fails | No |
| Installed | `--version` succeeds | No |
| Authentication failed | Official authentication-status command fails | No |
| Authentication unverified | CLI has no inexpensive authentication query | No; verify with the first real task |
| Authentication verified | Official authentication command succeeds | Describe authentication as verified |
| Execution verified | A real task returns a structured result under the shared protocol | Describe that specific task as successfully executed |

A CLI executable, an environment variable, or provider configuration in CC Switch does not establish that model requests work. A provider's success report does not establish that its SolidWorks/AutoCAD artifacts are correct.

## Shared task protocol

Use `agent_task` as the task type and `agent` as the executor:

```json
{
  "kind": "agent_task",
  "executor": "agent",
  "objective": "Create a mounting plate with counterbores and an obround slot",
  "skillPath": "C:/Users/user/.codex/skills/solidworks-automation/SKILL.md",
  "uiConfig": {
    "agentRuntime": {
      "provider": "claude",
      "providerName": "Claude Code",
      "protocol": "claude-print-v1",
      "model": ""
    }
  }
}
```

The legacy `codex_task` and `executor=codex` entries remain compatibility aliases; the worker normalizes them to the same execution flow.

## Shared result protocol

Each provider must ultimately return these fields:

```json
{
  "summary": "Work performed in this run",
  "changedFiles": [],
  "verification": [],
  "risks": [],
  "nextSteps": []
}
```

The shared result records agent execution; it is not CAD acceptance evidence. Mechanical delivery still requires independent file hashes, B-Rep dimensions, hole and slot locations, previews, Motion results, and human review records.

## Current adapters

| Provider | Protocol ID | Noninteractive entry point | Structured output source |
|---|---|---|---|
| Codex | `codex-exec-v1` | `codex exec` | `--output-schema` and output file |
| Claude Code | `claude-print-v1` | `claude -p` | `--output-format json` + `--json-schema` |
| Gemini CLI | `gemini-headless-v1` | `gemini -p` | JSON response wrapper |
| OpenCode | `opencode-jsonl-v1` | `opencode run` | JSONL text events |

Implementation:

- `apps/desktop/cad_workbench/agent_providers.py`
- `apps/desktop/cad_workbench/queue_worker.py`
- `apps/workbench-ui/src-tauri/src/lib.rs`

## Adding a provider

1. Register a stable ID in `SUPPORTED_PROVIDER_IDS` and the frontend `AgentProviderId`.
2. Use only noninteractive arguments confirmed by the CLI's official documentation; do not guess options from memory.
3. Compile shared tasks into provider commands in `build_provider_command()`.
4. Parse the native wrapper in `parse_provider_result()` and normalize the result to the shared fields.
5. Add tests for installation, authentication, timeouts, non-JSON output, missing fields, and cancellation.
6. Distinguish installation, authentication, and execution verification in desktop health checks; do not add an ambiguous connected Boolean.
7. Run a minimal real probe to verify exit codes, stdout/stderr, cancellation, and timeout behavior.

## Observable execution

The application can show plans, public steps, tool calls, approvals, logs, file changes, and review results. Do not promise or fabricate hidden model reasoning. Users need an auditable execution trace and conversation context they can continue questioning.

## Safety boundaries

- Provider adapters do not directly expose arbitrary Python, PowerShell, or VBA tools.
- Serialize CAD COM calls so multiple agents cannot operate the same desktop session concurrently.
- External network access, cloud RAG, and hazardous local CAD actions pass through the Policy Gate.
- Never write API keys into task JSON, logs, or frontend storage; record only redacted status or environment variable names.
- Provider output must pass schema validation, the Artifact Ledger, and the Reviewer Gate before delivery can be reported as successful.
