# SolidWorks ModelOps skill and entry point map

The root skill is `solidworks-modelops`, with `scripts/sw_modeling.py` as its unified entry point.
v0.1 is pilot: basic part creation, named linear dimension edits in task-owned copies, disk checkpoints,
and recovery to new copies. Inherited specialist scripts retain their own validation limits and do not
automatically receive the unified interface's checkpoint or recovery guarantees.

## Root entry points

| File | Responsibility |
| --- | --- |
| [SKILL.md](../SKILL.md) | Agent routing, write boundaries, and acceptance requirements |
| [README.md](../README.md) | Installation, complete CLI, scope, and tests |
| [agents/openai.yaml](../agents/openai.yaml) | Skill display metadata and default prompt |
| [scripts/sw_modeling.py](../scripts/sw_modeling.py) | `validate`, `run`, `inspect`, `checkpoints` |
| [scripts/sw_checkpoints.py](../scripts/sw_checkpoints.py) | Checkpoint publication, file hash verification, and copy-based recovery |
| [scripts/sw_modeling_regression.py](../scripts/sw_modeling_regression.py) | Regression suite for create, edit, failure recovery, and independent-process reopening |
| [capabilities.yaml](../capabilities.yaml) | Capability levels, limitations, and evidence scope |

Example requests: [create](../examples/modeling_create.json), [edit](../examples/modeling_edit.json),
and [restore](../examples/modeling_restore.json). Fill the edit and restore examples with actual source
and checkpoint information. The [regression suite](../examples/modeling_regression_suite.json) links
the fixtures generated during its run.

## Shared modules and specialist workflows

| Module or subskill | Use | Relationship to the unified interface |
| --- | --- | --- |
| `sw_closed_loop` / `sw_closed_loop_native` | Four-operation plans, bounded feedback, task-owned native parts | Create reuses the execution engine and native adapter |
| `sw_document_data` | Exact dimension names and readback | Edit reuses dimension updates and adds ownership and acceptance checks |
| `sw_sketch_constraints` | Ordinary and absorbed sketches, dimension and relation evidence | Supports delivery and recovery review |
| [solidworks-vibecad](../subskills/solidworks-vibecad/SKILL.md) | Natural-language requests to parametric plans | Use for planning; plans beyond the four-operation scope cannot go directly to the unified executor |
| [solidworks-fillet-chamfer-cnc](../subskills/solidworks-fillet-chamfer-cnc/SKILL.md) | CNC parts with many fillets/chamfers | Separate workflow; review its capability entry and actual reports |
| [solidworks-threaded-holes](../subskills/solidworks-threaded-holes/SKILL.md) | Threaded holes and thread representation | Separate workflow; distinguish cosmetic, reference-curve, and solid threads |
| [autocad-automation](../subskills/autocad-automation/SKILL.md) | AutoCAD and 2D delivery | Inherited specialist workflow outside the native-part transaction interface |

For assembly, Motion, drawing, FEA, and other tasks outside the unified interface, follow the root skill's
specialist routing and check the limits in [capabilities.yaml](../capabilities.yaml). A reference document's
presence is not evidence that its capability has been implemented or validated.

## Checks and extension

Run `python scripts/validate_skill.py` to check required files, root skill metadata, and Python/JSON syntax.
See [README.md](../README.md) for offline pytest and native regression commands. Report these checks
separately: package completeness and offline results do not establish native SolidWorks modeling success.

To add a unified operation, define its JSON validation and measurable acceptance criteria, implement
ownership, checkpoint, and failure recovery behavior, add offline and native regression cases, then
update the root SKILL, README, capability registry, and this map. Put independent specialist implementations
and resources in `subskills/<name>/` and update the same entry files. This repository does not use
`SUBSKILLS.md` or `project.yaml` as registration entry points.

## Inherited references

The [upstream automation guide](../references/upstream-automation-guide.md), CAD Studio product documents,
and desktop prototype retain technical context. Their names, release workflows, and homepages describe
the upstream project and are not download or installation entry points for ModelOps.
See [NOTICE.md](../NOTICE.md) for provenance and licensing.
