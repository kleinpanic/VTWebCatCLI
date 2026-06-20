# VTWebCatCLI

`VTWebCatCLI` is a local pre-submission checker for Virginia Tech Web-CAT
Java courses. The project still supports the original Python checker workflow,
and it is being extended with a profile-aware `webcat` runner for courses whose
grading model is materially different.

The goal is not "CS3114 replaces CS2505." The goal is one tool that can support
multiple VT classes through first-class course profiles.

## Repository Layout

- `bin/webcat`: the primary profile-aware CLI for CS2505, CS3114, and future
  course profiles.
- `lib/`: shell backend modules used by `bin/webcat`.
- `vtwebcatcli/classic.py`: the original Python checker implementation used
  for CS2505-style checks.
- `WebcatCLI.py`: root compatibility shim that dispatches to
  `vtwebcatcli/classic.py`.
- `profiles/`: course profile metadata.
- `templates/`: the single canonical location for rules files and bundled
  public course jars.
- `tests/`: all repo test harnesses.
- `docs/`: all user and developer documentation.
- `plugin/`: editor integration files.

## Command Surfaces

Classic VTWebCatCLI remains available:

```sh
python WebcatCLI.py --help
python WebcatCLI.py --run-tests /path/to/java-project
```

The profile-aware runner is:

```sh
bin/webcat doctor
bin/webcat test
bin/webcat mutate
bin/webcat report
```

Both command surfaces live in the same repository, but source has one
canonical home: `vtwebcatcli/classic.py` for the original Python checker and
`lib/` for the profile-aware runner used by `bin/webcat`. The root
`WebcatCLI.py` file is only a compatibility shim for existing CS2505 users.

## Current Course Profiles

- `cs2505`: VTWebCatCLI classic checks: style, Javadoc, test conventions,
  Maven/JUnit execution, and JaCoCo coverage parsing.
- `cs3114`: direct Java compile, `student.jar` JUnit tests, and PIT mutation
  testing with the course-specific mutator set. This is a local preflight, not
  a complete replacement for the official Web-CAT report yet.

Additional classes should be added as new profile directories under
`profiles/<course>/`, with course-specific logic isolated behind a backend
rather than blended into another course's assumptions.

## Status

Implemented now:

- original `WebcatCLI.py` entrypoint preserved;
- original public files and root paths preserved for normal `git pull` usage;
- classic checker relocated to `vtwebcatcli/classic.py` as first-class code;
- `webcat doctor`;
- `webcat test` for `cs3114`;
- `webcat mutate` for `cs3114`;
- `webcat report` for `cs3114`, with local checks plus explicit unsupported
  Web-CAT-only fields;
- `webcat test` bridge for `cs2505` through the classic VTWebCatCLI backend;
- `.webcat.toml` walk-up config loading;
- schema-versioned JSON output from the profile runner;
- GitHub Actions CI for the classic checker, classic Maven/JUnit/JaCoCo
  `--run-tests` path, and profile runner.

Not complete yet:

- broader CS2505 course fixtures through the `bin/webcat --profile cs2505`
  wrapper;
- Web-CAT authenticated `targets` and `submit`;
- CS3114 Web-CAT report parity: official style/readability scoring, problem
  coverage/reference-test comparison, final score math, early bonus display,
  and source-rendered report output;
- credential backends;
- Neovim commands;
- CS3114 jar vendoring/provenance completion.

## Project Config

Create `.webcat.toml` in the project root.

```toml
profile = "cs3114"
src = "Sum26P1MovieRater/src"
threshold = "90"
gate = "block"
assignment_path = "Virginia Tech/CS 3114/Project 1: Movie Rater"

java_bin = "/opt/homebrew/opt/openjdk@21/bin/java"
javac_bin = "/opt/homebrew/opt/openjdk@21/bin/javac"
student_jar = "lib/student.jar"
junit_jar = "tools/Eclipse.app/Contents/Eclipse/plugins/org.junit_4.13.2.v20240929-1000.jar"
hamcrest_jar = "tools/Eclipse.app/Contents/Eclipse/plugins/org.hamcrest_3.0.0.jar"
pit_dir = "tools/Eclipse.app/Contents/Eclipse/plugins/org.pitest_1.6.8.v20230703-1755/lib"

target_classes = "MovieRaterDB,SparseMatrix"
target_tests = "MovieRaterTest"
```

## Verification Notes

Local CS3114 Project 1 verification runs through `bin/webcat`, but it is not
the same thing as the full Web-CAT report. The current CLI does not reproduce
Web-CAT's hidden/reference problem coverage, official style/readability score,
final score calculation, early bonus, or rendered source report. Local PIT
output may also differ from Web-CAT because of instrumentation, mutation
targets, jars, or full-precision scoring. Do not quote a local percentage as
the official Web-CAT score unless it has been calibrated against the current
submission report.

See `docs/cs3114-webcat-parity.md` for the current CS3114 parity map.

## Development

Run local checks:

```sh
python -m py_compile vtwebcatcli/classic.py
python WebcatCLI.py --version
bash tests/classic-webcatcli.sh
bash tests/classic-run-tests.sh
bash tests/run.sh
bash tests/repo-health.sh
```

Validate profile-runner JSON:

```sh
bin/webcat doctor | python3 -m json.tool
bin/webcat --profile cs2505 doctor | python3 -m json.tool
bin/webcat --profile cs3114 doctor | python3 -m json.tool
```

## Adding A Course

See `docs/course-profiles.md`. A new course should add a profile, describe its
tools and thresholds, and implement only the backend behavior that actually
matches that course.

## Publishing

See `PUBLISHING.md`. The upgrade should land on `main` through the existing
`kleinpanic/VTWebCatCLI` repository history, not as an unrelated replacement.
