# Course Profiles

Course profiles keep VTWebCatCLI useful across classes without pretending that
different courses use the same grader.

## Rule

Shared code should handle config, JSON, process execution, path resolution,
credential lookup, and editor integration. Course-specific grading behavior
belongs in a profile backend.

## Profile Layout

Each profile lives at:

```text
profiles/<course>/profile.conf
```

Current examples:

```text
profiles/cs2505/profile.conf
profiles/cs3114/profile.conf
```

The profile declares:

- supported commands;
- test, style, coverage, and mutation backends;
- compile release;
- required tools;
- jar expectations;
- default threshold;
- course-specific options such as PIT mutators or classic rules.

## Adding A New Class

1. Create `profiles/<course>/profile.conf`.
2. Pick existing backend behavior only if it truly matches the course.
3. Add a new backend script when the course has different requirements.
4. Add test coverage in `tests/run.sh`.
5. Update `README.md` with the course and verification status.
6. Record any required jars in `PROVENANCE.md` before committing binaries.

## Backend Guidance

Do not blend course assumptions.

- CS2505 uses classic VTWebCatCLI style/Javadoc/test-convention checks plus
  Maven/JUnit/JaCoCo behavior.
- CS3114 uses direct Java compilation, `student.jar` JUnit tests, JaCoCo
  coverage over configured target classes, and PIT mutation with a
  course-specific mutator set.

If another VT course differs from both, it should get its own backend.

## Score Caveat

Local checks are meant to reduce submission risk, not redefine Web-CAT's score.
Whenever local output differs from Web-CAT, record both values and investigate
the target classes, jars, hidden/reference checks, mutation engine version,
mutator set, and rounding/full-precision behavior.
