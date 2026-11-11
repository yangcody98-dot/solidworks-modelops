# Enterprise agents and mechanical knowledge retrieval

## Target architecture

CAD Studio uses a control plane, deterministic CAD tools, a Reviewer Gate, and local-first RAG:

```text
User conversation / UI configuration
  -> Intake / Planner
  -> Local knowledge retrieval (default)
  -> Optional cloud retrieval (explicit enablement and external-network approval)
  -> Codex Executor
  -> Serialized SolidWorks / AutoCAD tools
  -> Artifact Ledger
  -> Reviewer Gate
  -> Human review and continued conversation
```

`apps/desktop/cad_workbench/knowledge_retrieval.py` implements:

- Retrieval from the main `SKILL.md`, `references/`, all subskill references, and knowledge files.
- Chinese/English token search, chunking, and Top-K ranking.
- Source path, content SHA-256, score, and provider for every passage.
- Automatic worker injection of retrieved passages into enterprise prompts.
- An optional HTTPS cloud RAG connector whose token comes only from the environment.

## Data boundaries

1. Retrieve only local skill knowledge by default. Do not upload user projects, models, drawings, or prompts.
2. Cloud retrieval must explicitly declare `external_network` in the task and receive human approval.
3. Cloud endpoints must use HTTPS. Do not write tokens into task JSON, logs, or persisted UI files.
4. The token environment variable is fixed to `CAD_STUDIO_RAG_TOKEN`; tasks cannot name another variable and exfiltrate unrelated credentials.
5. Custom local knowledge directories trigger cross-workspace access approval. Direct queue-file writes do not bypass this gate.
6. Retrieved passages are references, not substitutes for the original GB/T or ISO standard, material handbook, supplier catalog, or company standard.
7. Preserve `source` and `sha256`; untraceable passages cannot support manufacturing gates.

## Task configuration

```json
{
  "uiConfig": {
    "knowledgeBase": {
      "topK": 6,
      "localRoots": ["D:/company-cad-standards"],
      "cloudEnabled": false,
      "endpoint": "https://rag.example.com/retrieve",
      "namespace": "mechanical-engineering",
      "tokenEnv": "CAD_STUDIO_RAG_TOKEN"
    }
  }
}
```

Cloud response contract:

```json
{
  "chunks": [
    {
      "title": "Bearing housing bore fits",
      "source": "enterprise-standard://bearing/fit-v3",
      "text": "Retrievable source passage",
      "score": 0.91
    }
  ]
}
```

## Knowledge layers

- `L0 Session facts`: user dimensions, purpose, material, loads, manufacturing process, and target software.
- `L1 Project knowledge`: current drawings, parameter tables, BOM, company standards, and revision history.
- `L2 Skill knowledge`: repository references, specialized subskills, and verified API lessons.
- `L3 Organization knowledge`: approved templates, failure cases, process capabilities, and supplier constraints.
- `L4 External knowledge`: official APIs, national/industry standards, and vendor manuals; preserve versions and sources.

Retrieval priority is `L0 > L1 > L2 > L3 > L4`. Stop automatic execution on conflicts and send them to the Reviewer; never silently choose one source.

## Gates before cloud deployment

- Separate tenant namespaces and use least-privilege tokens.
- Enforce document ACLs before retrieval, not only after answer generation.
- Keep immutable audit records for uploads, deletions, and reindexing.
- Redact PII, secrets, customer drawing watermarks, and controlled technical material on the client.
- Support source revocation, version rollback, expiration, and citation-hit statistics.
- Mark standard numbers, materials, tolerances, and safety factors as requiring original-source review.
