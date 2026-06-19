# VTWebCatCLI

`VTWebCatCLI` is a local pre-submission checker for Virginia Tech Web-CAT
Java courses. The project still supports the original Python checker workflow,
and it is being extended with a profile-aware `webcat` runner for courses whose
grading model is materially different.

The goal is not "CS3114 replaces CS2505." The goal is one tool that can support
multiple VT classes through first-class course profiles.

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
```

Both command surfaces live in the same repository. The classic checker keeps
the original style/Javadoc/test-convention/Maven/JaCoCo behavior. The newer
`bin/webcat` command provides JSON output for editor and CI integration.

## Current Course Profiles

- `cs2505`: VTWebCatCLI classic checks: style, Javadoc, test conventions,
  Maven/JUnit execution, and JaCoCo coverage parsing.
- `cs3114`: direct Java compile, `student.jar` JUnit tests, and PIT mutation
  testing with the course-specific mutator set.

Additional classes should be added as new profile directories under
`profiles/<course>/`, with course-specific logic isolated behind a backend
rather than blended into another course's assumptions.

## Status

Implemented now:

- original `WebcatCLI.py` entrypoint preserved;
- original public files and root paths preserved for normal `git pull` usage;
- classic checker relocated to `vtwebcatcli/classic/` as first-class code;
- `webcat doctor`;
- `webcat test` for `cs3114`;
- `webcat mutate` for `cs3114`;
- `webcat test` bridge for `cs2505` through the classic VTWebCatCLI backend;
- `.webcat.toml` walk-up config loading;
- schema-versioned JSON output from the profile runner;
- GitHub Actions CI for the classic checker, classic Maven/JUnit/JaCoCo
  `--run-tests` path, and profile runner.

Not complete yet:

- broader CS2505 course fixtures through the `bin/webcat --profile cs2505`
  wrapper;
- Web-CAT authenticated `targets` and `submit`;
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

Local CS3114 Project 1 verification runs through `bin/webcat`, but local PIT
output is not the same thing as the Web-CAT mutation percentage. Web-CAT may
use different instrumentation, hidden/reference checks, mutation targets, or
full-precision scoring. Do not quote a local percentage as the official Web-CAT
score unless it has been calibrated against the current submission report.

## Development

Run local checks:

```sh
python -m py_compile vtwebcatcli/classic/WebcatCLI.py
python WebcatCLI.py --version
bash vtwebcatcli/classic/tests/test_webcatcli.sh
bash test/classic-run-tests.sh
bash test/run.sh
bash test/repo-health.sh
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
