# Mutation Accuracy Audit

Date: 2026-06-19

## Verdict

`bin/webcat mutate` is accurate for a fresh local PIT invocation. It is not the
same thing as official Web-CAT mutation scoring.

A fresh Project 1 rerun from the current working tree reported:

```text
156/158 killed, 98.7%
```

The two non-killed rows were both exact PIT status
`LINES_NEEDING_BETTER_TESTING`:

- `SparseMatrix.java:461`, `colScore`,
  `RemoveConditionalMutator_EQUAL_ELSE`
- `SparseMatrix.java:416`, `rowScore`,
  `RemoveConditionalMutator_EQUAL_ELSE`

## What Was Wrong

The previous JSON summarizer counted every non-`KILLED` PIT row as `survived`.
That was too loose. PIT can report more specific statuses, and consumers need to
see the actual bucket before deciding what to fix.

## What The CLI Reports Now

Mutation JSON now includes:

- exact status counts from the PIT CSV;
- `killed`, `survived`, `no_coverage`, `timed_out`, `memory_error`,
  `run_error`, `non_viable`, `other`, and `undetected`;
- target classes and target tests;
- whether target classes/tests were explicit or inferred;
- the formula used for the percentage: `killed / total`.

The old `survivors` array is still present for compatibility, but consumers
should prefer `status_counts`, `coverage.undetected`, and `undetected`.

## Web-CAT Limit

The CLI cannot currently prove Web-CAT-only data:

- hidden/reference-test correctness;
- problem coverage;
- valid test percentage;
- official style/readability score;
- final score and early bonus;
- authenticated submission or official report retrieval.

Local PIT and JaCoCo are therefore labeled as uncalibrated partial checks in the
`webcat report` parity block.
