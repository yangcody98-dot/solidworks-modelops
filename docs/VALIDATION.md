# v0.1 validation record

Date: 2026-11-10. Environment: Windows, Python 3.12, SolidWorks 2025 SP2.0 (revision 33.2.0).
These results come from the recorded local run. Check the repository's Actions page separately for GitHub Actions status.

## Offline and interface checks

- The seven explicitly listed offline test files: **242 passed, 1 skipped**.
- The skipped case requires creating a real symbolic link, which this machine did not permit. Simulated reparse-path rejection tests passed.
- Skill structure, Python/JSON syntax, and example request validation passed.
- MCP protocol inventory validation passed: 41 visible tools, including 4 unified ModelOps tools.

## Native CAD regression suite

Fixture: a 100 × 60 mm plate with four Ø6 through holes, centered at (±40, ±20) mm.
The independent analytical volume is `(100×60 − 4π×3²)×thickness`; volume tolerance is 0.1 mm³, and bounds, hole-position, and hole-diameter tolerances are 0.05 mm.

| Case | Executed behavior | Result |
|---|---|---|
| Create | Generate the 8 mm four-hole plate; check geometry, full sketch definition, native output, and reopened STEP | Passed |
| Edit dimension | Change thickness from 8 to 12 mm in a disk copy; read back dimensions and geometry | Passed |
| Recover failed edit | Actually change thickness to 14 mm, fail an intentionally incorrect volume requirement, then restore to 12 mm | Expected failure and recovery both verified; the original edit task remains unsuccessful |
| Restore in an independent process | Read the checkpoint in a new Python process, reopen the native copy, and export again for validation | Passed |

All four cases passed the original-session protection checks. These cover the COM identities, metadata,
readable selection states, and enumerated disk files of all original documents. Geometry and features
were additionally compared for the original active document. No complete geometry audit was performed
for all background documents; unenumerated references are outside the verified scope.

This work also covered preflight handling for a large assembly with more than 1,000 loaded documents,
fallback lookup using internal assembly names, and recognition of the same Windows file after SolidWorks
normalizes its extension to uppercase. Corresponding offline regression tests are retained in the native adapter test suite.

The public [machine-readable summary](validation/2026-11-10.json) contains only the fixture specifications
and check results. Original reports contain local project paths and are excluded from the public source release.
These results do not establish support for other SolidWorks versions, configuration families, parts with
external references, assembly editing, or arbitrary complex mechanical designs. The capability remains **pilot**.

## English documentation and showcase refresh — 2026-11-11

The same seven-file offline test set was rerun: **242 passed, 1 skipped**. Skill validation, UTF-8 skill metadata validation, all three example request validators, and regression-suite contract validation passed. The four-case native transaction results above remain the recorded 2026-11-10 run.

The new independent XY-stage showcase was imported and previewed in SolidWorks 2025 SP2.0. It contains 226 components; 21 source prototypes passed OCCT validity and positive-volume checks. Component colors were read back successfully, and the original active document state and working directory were restored. These are visualization and session checks; full assembly geometry measurements, mates, fit, motion, and loads were not validated. See [SHOWCASE.md](SHOWCASE.md) for the reproduction procedure and evidence scope.
