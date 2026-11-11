# Provenance and additions

SolidWorks ModelOps includes code, documentation, and resources inherited and adapted from:

- **SolidWorks Automation Skill**
- Upstream repository: <https://github.com/wzyn20051216/solidworks-automation-skill>
- Upstream license: MIT License
- Original copyright: `Copyright (c) 2026 SolidWorks Automation Skill Contributors`

The original copyright and complete MIT license are preserved in [LICENSE](LICENSE).
Retain these notices in copies or substantial portions of the software.

## Inherited work

This repository inherits the upstream SolidWorks connection, part, sketch constraint, document data,
closed-loop execution, review, and export modules, together with related specialist workflows,
references, and tests. Their inclusion does not automatically establish verified support in this
release's unified interface.

## ModelOps additions

This work adds or integrates:

- A unified JSON modeling request interface and validation.
- Bounded part creation and precisely named linear dimension editing.
- Task-owned working copies, disk checkpoints, and recovery with hash verification.
- A regression suite interface, related offline tests, release documentation, and CI configuration.

These additions and retained upstream modules form v0.1 pilot. Current source code, [README.md](README.md),
and actual run reports define the behavior, limits, and validation results. This notice does not claim
the upstream work as original ModelOps development or describe planned features as completed.

SolidWorks is a trademark of Dassault Systèmes SolidWorks Corporation. This project is independently
maintained and is not provided, endorsed, or certified by that company. Users must hold an applicable
license to use native SolidWorks functionality.
