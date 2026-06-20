# CS3114 Web-CAT Parity

This document compares the current `cs3114` profile with the official
Web-CAT Project 1 report saved as `/Users/collins/Downloads/Web-CAT.pdf` on
2026-06-19.

## Current Verdict

`bin/webcat --profile cs3114` is a useful local pre-submission checker, but it
does not yet replace the official CS3114 Web-CAT report.

The current CLI proves:

- Java compilation with the configured Java release.
- Student JUnit tests through `student.jar`.
- Local PIT mutation coverage for configured target classes and tests.
- A `report` command that combines local checks and explicitly labels
  Web-CAT-only fields as unsupported.
- JSON output suitable for editor or CI consumption.

The current CLI does not prove:

- Hidden/reference-test correctness.
- Web-CAT's problem coverage comparison.
- Official Web-CAT style/readability scoring.
- Official final-score calculation, early bonus, or staff-awaiting state.
- Source-rendered report pages with per-file remarks/deductions.
- Authenticated submission to Web-CAT.

Those unsupported items can be improved in two different ways:

- Local reproduction: source report generation, conservative submission-shape
  checks, local style checks, and local score modeling can be implemented
  without Web-CAT credentials.
- Web-CAT integration: hidden/reference correctness, problem coverage,
  official style scoring, early bonus, and final score require either an
  authenticated Web-CAT submission/report retrieval path or instructor-owned
  reference artifacts.

## Report Surface Comparison

| Web-CAT report surface | Official report example | Current CLI status |
| --- | --- | --- |
| Assignment metadata | course, project, try number, student, partners, submitted time | Missing |
| Total score | `60.0 + 10.0 early bonus = 70.0/110.0` | Missing |
| Design/readability | `/50.0 <Awaiting Staff>` | Missing |
| Style/coding | `10.0/10.0` plus per-file remarks/deductions | Missing |
| Correctness/testing | `50.0/50.0` | Partial, inferred only from public tests and local mutation |
| Per-file mutation | `MovieRaterDB.java 100.0%`, `SparseMatrix.java 93.8%` | Partial, local PIT survivors and aggregate percent only |
| Problem coverage | `100%` from reference-test comparison | Missing, depends on Web-CAT reference implementation |
| Valid test percentage | `100%` from running tests against reference implementation | Missing, depends on Web-CAT reference implementation |
| Student test run | pass/failure/error counts for submitted tests | Matched for local JUnit test execution |
| Mutation score formula | `tests * mutants * problem coverage * points` | Missing as official score math |
| Full-precision scoring note | Web-CAT uses unrounded percentages | Missing |
| Rendered source listing | all submitted source files displayed in report | Missing |

## Current Project 1 Calibration

Using the current Project 1 working tree:

```text
bin/webcat test
```

reports:

```text
44 total, 44 passed, 0 failed
```

```text
bin/webcat mutate
```

reports:

```text
160/162 killed, 98.8%
```

```text
bin/webcat report
```

returns local test and mutation JSON plus a `webcat_parity` block. That block
is deliberately explicit about unsupported official Web-CAT fields so consumers
do not mistake the local report for the official grader report.

The official PDF report for an earlier submission reported `93.8%` for
`SparseMatrix.java` and `100.0%` for `MovieRaterDB.java`. Those values are not
directly interchangeable with the local CLI result because the local run uses
the current working tree and a local PIT invocation, while Web-CAT uses its own
submission snapshot, instrumentation, targets, reference-test comparison, and
full-precision scoring.

## Required Work For Replacement-Level CS3114 Support

1. Add source-report generation so users can inspect the exact submitted files
   and line numbers like Web-CAT does.
2. Add conservative local submission checks for flat `src`, Java 11, forbidden
   data structures, source line limits, and pledge presence.
3. Add local score modeling for the pieces the CLI can actually compute.
4. Add a style backend for the CS3114 checkstyle/readability rules once the
   course's actual style checker is identified or reproduced.
5. Add authenticated `targets`, `submit`, and report retrieval support if the
   tool is meant to
   replace the Eclipse/Web-CAT submission route.
6. Calibrate mutation target selection and PIT/JUnit jars against current
   Web-CAT reports before presenting local mutation percentages as comparable.

Until those items are implemented, `cs3114` should be described as a local
preflight and mutation aid, not a Web-CAT replacement.
