# VTWebCatCLI

`VTWebCatCLI` is a profile-aware local Web-CAT helper for Virginia Tech Java
courses. It is being upgraded from the older CS2505-style `VTWebCatCLI` into a
tool that can support materially different course workflows through separate
profiles.

Current profiles:

- `cs2505`: legacy VTWebCatCLI direction: style/Javadoc conventions,
  Maven/JUnit, and JaCoCo coverage.
- `cs3114`: direct Java 11 compile, `student.jar` JUnit tests, and PIT 1.6.8
  mutation testing with Web-CAT's CS3114 mutators.

The CLI executable is `bin/webcat`. The optional Neovim module will live in the
same repository under `lua/webcat/`, but it must remain a thin consumer of the
CLI's `schema:1` JSON output.

## Status

Implemented now:

- `webcat doctor`
- `webcat test` for `cs3114`
- `webcat mutate` for `cs3114`
- timeout-wrapped `webcat test` bridge for the imported legacy `cs2505`
  VTWebCatCLI backend
- profile loading from `.webcat.toml`
- JSON output suitable for editor/CI consumption
- GitHub Actions CI for CLI smoke tests, profile separation, and a hermetic
  CS3114 direct-JUnit fixture
- imported legacy `VTWebCatCLI` static/style harness validation in CI

Not implemented yet:

- fully verified CS2505 Maven/JUnit/JaCoCo coverage execution in CI
- Web-CAT `targets` and `submit`
- credential backends
- Neovim commands
- jar vendoring/provenance completion

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

## Commands

```sh
bin/webcat doctor
bin/webcat test
bin/webcat mutate
```

Each command emits one JSON object on stdout.

Example verified against the local CS3114 Project 1:

```text
doctor: ok, no missing jars
test:   37 passed, 0 failed
mutate: 155 killed, 5 survived, 160 total, 96.9%
```

## Development

Run the local smoke tests:

```sh
bash test/run.sh
```

Validate command output:

```sh
bin/webcat doctor | python3 -m json.tool
```

The test harness exercises:

- profile metadata for `cs2505` and `cs3114`,
- config walk-up discovery,
- CS2505 legacy wrapper JSON output,
- unsupported CS2505 mutation behavior,
- a real CS3114 compile + JUnit invocation fixture with comma-separated tests.

CI also runs the imported legacy harness:

```sh
bash legacy/VTWebCatCLI/tests/test_webcatcli.sh
```

That protects the original CS2505-style static checks while the new
profile-aware wrapper grows around them.

## Publishing

See `PUBLISHING.md`. The existing public GitHub repo
`kleinpanic/VTWebCatCLI` has its own `main` history, so this upgrade should be
pushed to a review branch first, not force-pushed over `main`.

## Naming

Canonical product/repo spelling should be `VTWebCatCLI`, matching the original
repository. The local folder may still be named `cs3114-webcat` until the rename
and GitHub migration are explicitly confirmed.
