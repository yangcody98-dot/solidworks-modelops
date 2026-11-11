# SolidWorks Automation Skill market research — historical positioning

Research date: 2026-07-25.

> Inherited upstream research and product proposals. Market figures, product descriptions, suggested defaults, and targets are historical source material, not refreshed recommendations or ModelOps validation results. This document does not define the current ModelOps capability contract; use [README](../README.md) and [capabilities.yaml](../capabilities.yaml).

## 1. Proposed direction

The proposed product was a local CAD delivery assistant for mechanical engineers and prototyping teams: reference images/parameters → modeling → engineering drawings → GB/T and manufacturing-rule review → delivery package. The intended value lay in repetitive work around SolidWorks, Inventor, Fusion, NX, and Creo, without building a competing CAD kernel or a presentation-only shell.

## 2. Historical market signals and interpretation

The 2026 Research and Markets report segmented CAD by 3D/2D, deployment, modeling approach, and industry, including engineering and industrial-design firms. The cited 2025 Zhiyan Consulting report estimated the 2024 industrial R&D/design software market at about USD 55 billion worldwide and RMB 35 billion in China, with smart manufacturing, digital transformation, and domestic substitution as drivers. These are retained source claims, not newly verified estimates. The proposed response was automation around established CAD rather than the cost of a complete replacement.

CoLab's 2026 overview grouped AI opportunities into knowledge management, generative design/AI CAD, simulation, design review/DFM, and PLM/digital thread. The suggested entry point was design review/DFM, drawing automation, and local engineering knowledge/rules, because inputs, rules, and deliverables can be inspected.

The research described SOLIDWORKS embedded AI/Virtual Companions/AURA/LEO, Fusion design/simulation/generative design/mesh/plastics/lifecycle tools, and AutoCAD Mechanical 2026 BOM/parts lists/balloons/automatic dimensions/GD&T/standard annotations. The proposed niche combined Windows-local workflows, Chinese engineering conventions, GB/T review, SolidWorks–AutoCAD integration, small-batch/3D-print delivery, and agent-callable operations.

## 3. Competitor observations at the research date

| Product/direction | Observed focus | Lesson | Proposed boundary |
| --- | --- | --- | --- |
| SOLIDWORKS AI | Embedded AI, companions, workflow assistance | Demand for CAD-native assistance | No new CAD kernel |
| Autodesk Fusion | CAD, simulation, generative design, lifecycle | Design-to-manufacturing integration | No cloud-wide CAD platform |
| AutoCAD Mechanical | Mechanical drafting, standard annotations, BOM | Standards and annotation matter | No AutoCAD replacement |
| Siemens Solid Edge 2D Drafting | 2D drawings, dimensions, standard compatibility | Continued demand for 2D engineering | No standalone 2D CAD |
| DraftAid | 3D-to-2D manufacturing drawings | Drawing automation is a strong need | Do not limit support to foreign standards/English |
| CoLab AutoReview | Review, DFM, issue tracking, knowledge | Review fits enterprise workflows | No large collaboration platform first |
| Leo AI | CAD-aware engineering knowledge | Reuse engineering knowledge | No unsupported claims of complex B-rep semantics |
| Zoo.dev | Text-to-CAD, geometry engine, APIs | Text interfaces are relevant | No self-developed geometry kernel |

## 4. Users and pain points

Primary users were individual mechanical designers, makers, small studios, automation engineers, and 3D-print prototyping users. They used SolidWorks/AutoCAD for enclosures, brackets, plates, panels, and heat-dissipation housings; needed STL/STEP/DWG/DXF/PDF; and repeatedly modeled holes, chamfers, bosses, and drawings. Secondary users were small manufacturers, custom automation teams, and training organizations seeking consistent drawing practices, fewer novice errors, templates, and shorter prototype lead time.

Large automotive/aerospace/defense PLM, advanced surfacing/topology optimization, cloud collaboration, and full SolidWorks/NX/CATIA replacement were not priorities.

| Pain point | Example | Proposed automation |
| --- | --- | --- |
| Repeated modeling | Similar enclosure/bracket/panel dimensions | Parametric templates |
| Drawing rework | Missing hole location, crossed leaders, overlaps | GB/T review engine |
| Unprintable models | Thin walls, uncut holes, compensation/clearance errors | Print-process rules |
| Fragmented exports | Separate STL/STEP/DWG/DXF/PDF/preview steps | Delivery packaging |
| Lost experience | Senior engineers' rules remain informal | Rules and project reviews |
| Incomplete prompts | Missing datums/tolerances/materials | Structured forms and clarification |
| Disconnected software | Modeling, drafting, and file management split | Local orchestration |

At this historical stage, assets included SolidWorks scripts, AutoCAD subskills, drawing lessons, hole/slot/location rules, a GitHub skill repository, early MCP server, and examples/tests. Gaps were a user task entry, structured templates, formal GB/T and DFM/printing rules, stable review schema, project history, and a packaged Windows application.

## 5. Proposed MVP

Working title: CAD Automation Delivery Workbench. The first complete workflow would create a printable enclosure and engineering drawings following Chinese mechanical drafting conventions.

Required stages were project creation/reference upload; structured dimensions, wall thickness, fillets/chamfers, display/interface/screw/fluid-port/vent features; actual SolidWorks cuts and STL/STEP/SLDPRT; SolidWorks Drawing or AutoCAD DWG/DXF/PDF/PNG; A3/A4 border/title/scale/mm; automatic plus visual review; and an archived package with `review.json` and `README_DELIVERY.md`.

Cloud accounts, collaboration, PLM/PDM, topology optimization, complex surface generation, quoting, and arbitrary fully automatic CAD generation were deferred.

## 6. Review priorities

**P0:** Every hole, slot, interface, fluid port, screw hole, and boss needs specification, quantity, and location. Long leaders cannot substitute for dimension chains or cross views, holes, centerlines, or title blocks. Dimensions cannot obscure lines/text/borders. Include borders, title, units, scale, named views, and technical requirements. Required openings must be actual model cuts.

**P1:** Use hole/slot tables in dense areas, datum dimensions/centerlines for symmetric features, `n×Φd` or tables for repeated holes, process compensation guidance, and fit-clearance suggestions.

**P2:** Detect underdefined sketches, thin walls, sharp edges, overhangs, isolated small features, STL nonmanifold geometry/reversed normals/open edges, and generate DFM recommendations.

## 7. Proposed FDM starting rules

These were configurable starting suggestions, not universal manufacturing limits. Printer, material, nozzle, and slicing settings must govern the final profile.

| Item | Historical proposal |
| --- | --- |
| Structural wall | Prefer at least 1.6 mm |
| Minimum printable wall | At least 0.8–1.0 mm, nozzle-dependent |
| Boss outer diameter | At least 2–2.5 times screw diameter; refine for M2/M3/M4 |
| Hole compensation | Optional 0.2–0.4 mm allowance for undersized FDM holes |
| Sliding/insertion clearance | 0.2–0.5 mm |
| Horizontal round holes | Suggest teardrops or support |
| Precise small holes | Suggest drilling/reaming after printing |

## 8. Product form and proposed validation targets

The proposed first stack was PySide6 + Python automation + local project directories + GitHub skill updates, with no rented server. This reused COM/scripts, supported executable packaging, and kept engineering data local. Tauri/Electron with a local Python backend was a possible later UI.

| Metric | Proposed target, not a measured result |
| --- | --- |
| Enclosure to STL | Within 10 minutes |
| Drawing draft | Within 5 minutes |
| P0 missing hole/slot annotations | 0 |
| Print checks | Wall, diameter, actual cuts, clearance |
| Rework | At most 1 round |
| Input | Forms primary, prompts supplementary |

## 9. Proposed 90-day roadmap

- Weeks 1–2: `apps/desktop` or standalone PySide6 skeleton; project/output/logs and local skill/version status.
- Weeks 3–4: enclosure form, SolidWorks integration, STL/STEP/SLDPRT, actual-hole verification.
- Weeks 5–6: AutoCAD/SolidWorks Drawing, DWG/DXF/PDF/PNG, P0 review, `review.json`.
- Weeks 7–8: packaged files, delivery notes, history, visible failure reasons.
- Weeks 9–12: mounting plate, bracket, heat-dissipation enclosure, boss/insert templates, configurable print rules.

Risks were COM instability (serial tasks, bounded retry/timeouts), incomplete dimensions (required fields/clarification), imperfect automatic drafting review (P0 plus visual gates), company-specific conventions (configurable templates), printer variability (profiles), and scope growth (prioritize common enclosures/brackets/mounts).

The proposed next artifact was `docs/product-mvp-spec.md`, covering navigation, enclosure wizard, fields, files, `review.json`, P0 checks, and UI sketches before a PySide6 prototype.

## 10. Retained research sources

Sources below are preserved from the 2026-07-25 research; availability and current applicability have not been revalidated by this translation.

- [Research and Markets: CAD Software Market Report 2026](https://www.researchandmarkets.com/reports/5972859/computer-aided-design-cad-software-market-report)
- [Zhiyan Consulting: 2025 China industrial R&D/design software industry report](https://www.chyxx.com/industry/1217927.html)
- [SOLIDWORKS: AI Product Design with Embedded AI Tools](https://www.solidworks.com/product/solidworks-design/ai-overview)
- [SOLIDWORKS: AI CAD Tools for Workflow Optimization](https://www.solidworks.com/solution/solidworks-ai-cad-tools-workflow-optimization)
- [Autodesk Fusion: Design AI solutions](https://www.autodesk.com/solutions/generative-design-ai-software)
- [Autodesk AutoCAD Mechanical Toolset](https://www.autodesk.com/products/autocad/included-toolsets/autocad-mechanical)
- [Siemens Solid Edge 2D Drafting](https://resources.sw.siemens.com/en-US/download-free-2d-cad-software/)
- [CoLab: Best AI Tools & Agents for Mechanical Engineers 2026](https://www.colabsoftware.com/ai-tools-for-mechanical-engineers-guide)
- [CoLab: Design for Manufacturability Reviews](https://www.colabsoftware.com/use-case/design-for-manufacturability)
- [DraftAid: AI CAD Drawing Automation](https://draftaid.io/)
- [Zoo.dev: Zookeeper and Text-to-CAD](https://zoo.dev/zookeeper)
- [Leo AI: Engineering-grade AI for mechanical engineers](https://www.getleo.ai/)
- [National standards: GB/T 4458.4-2003, mechanical drawing dimensioning](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=08588A5F3FE19F16B9EE8D5D87E064D5)
- [National standards: GB/T 4457.4-2002, mechanical drawing lines](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=5B789BF5B537CF6F89B5D743DA71D883)
- [National standards: GB/T 10609.1-2008, technical drawing title blocks](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=0F8577CB9AB82D5819048A87920CABAB)
- [JLC3DP: 3D Printing Design Guideline](https://jlc3dp.com/help/article/3d-printing-design-guideline)
- [Prusa: Modeling with 3D printing in mind](https://help.prusa3d.com/article/modeling-with-3d-printing-in-mind_164135)
- [Formlabs: Minimum Wall Thickness for 3D Printing](https://formlabs.com/blog/minimum-wall-thickness-3d-printing/)
