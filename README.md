# WebcatCLI

**WebcatCLI** is a self-contained Python tool that performs preliminary Web-CAT–style checks on your Java projects before you submit. It enforces:

- **Style & Formatting**  
  - Spaces vs. tabs, configurable indentation width  
  - Maximum line length  
  - Javadoc presence & tags (`@author`, `@version`)  
  - One public class/interface per file  
  - No static (global) fields  
  - No empty methods or unused private methods  
  - *(Configurable)* `@Override` on all overridden methods  

- **Testing Conventions**  
  - Test-method naming prefix (default: `test`)  
  - *(Configurable)* must use `@Test` annotations  
  - Require three-argument `assertEquals` when comparing doubles  

- **Build & Coverage**  
  - Auto-generates a minimal `pom.xml` (JUnit 4 & JaCoCo)  
  - `--run-tests` invokes `mvn clean test` and enforces 100% JaCoCo method & branch coverage  
  - `--run-main` will locate and run your `main()` method after tests  

---

## Table of Contents

1. [Prerequisites](#prerequisites)  
2. [Installation](#installation)  
3. [Directory Layout](#directory-layout)  
4. [CLI Usage & Flags](#cli-usage--flags)  
5. [Rule Templates](#rule-templates)  
6. [Examples](#examples)  
7. [Running the Built-in Test Suite](#running-the-built-in-test-suite)  
8. [License](#license)  

---

## Prerequisites

- **Python 3**  
- **Java 8+** & **Maven** (for `--run-tests`)  
- A UNIX-style shell (for the provided test script)  

---

## Installation

1. Clone or download this repository.  
2. In the project root, make the CLI executable:

```bash
chmod +x WebcatCLI.py
````

3. (Optional) Add it to your `PATH`:

```bash
export PATH="$PATH:/path/to/WebcatCLI"
```

## Directory Layout

```
WebcatCLI/
├── WebcatCLI.py
├── README.md
├── test_webcatcli.sh        ← automated test harness
└── templates/
    ├── default.rules.json
    ├── CS1114.rules.json
    └── CS2114.rules.json
```

* **`templates/*.rules.json`**
  Per-profile rule definitions. See below for schema.

---

## CLI Usage & Flags

```bash
./WebcatCLI.py [OPTIONS] [PROJECT_ROOT]
```

* If `PROJECT_ROOT` is omitted, reads a single Java file from **stdin**.
* Exit codes:

  * `0` — all checks passed
  * `1` — style/test failures
  * `>1` — internal error

### Key Options

| Flag                   | What it does                                                   |
| ---------------------- | -------------------------------------------------------------- |
| `-p, --profile <name>` | Load `templates/<name>.rules.json` (default: CS2114)           |
| `--max-line-length N`  | Override max characters per line (`-1` disables)               |
| `--no-javadoc`         | Skip *all* Javadoc presence checks                             |
| `--no-author`          | Skip `@author` tag check                                       |
| `--no-version`         | Skip `@version` tag check                                      |
| `--allow-globals`      | Allow static (global) fields                                   |
| `--allow-empty`        | Allow empty method bodies                                      |
| `--allow-unused`       | Allow unused private methods                                   |
| `--no-annotations`     | Skip checking for `@Test` annotations                          |
| `--no-delta`           | Skip requiring delta in `assertEquals`                         |
| `--no-method-cov`      | Disable 100% method coverage enforcement                       |
| `--no-branch-cov`      | Disable 100% branch coverage enforcement                       |
| `--no-override`        | Disable enforcement of `@Override` on overridden methods       |
| `--run-tests`          | After style/test, run `mvn clean test` & parse JaCoCo coverage |
| `--run-main`           | After tests, detect & run your `main()` entrypoint             |

---

## Rule Templates

Each JSON rule file looks like this:

```jsonc
{
  "style": {
    "indentation": { "use_spaces": true, "spaces_per_indent": 4 },
    "max_line_length": 80,
    "no_tabs": true,
    "javadoc_required": true,
    "javadoc_require_author": true,
    "javadoc_require_version": true,
    "one_public_class_per_file": true,
    "disallow_global_variables": true,
    "no_empty_methods": true,
    "no_unused_methods": true,
    "require_override": true      // NEW: whether to enforce @Override
  },
  "testing": {
    "test_methods_prefix": "test",
    "annotation_required": false,
    "require_assert_equals_delta": true,
    "require_full_method_coverage": true,
    "require_full_branch_coverage": true
  }
}
```

---

## Examples

```bash
# Basic style & test checks
./WebcatCLI.py ~/my-java-project

# Skip Javadoc & author/version checks
./WebcatCLI.py --no-javadoc --no-author ~/my-java-project

# Temporarily allow longer lines
./WebcatCLI.py --max-line-length 200 ~/my-java-project

# Enforce full coverage and run tests
./WebcatCLI.py --run-tests ~/my-java-project

# Disable @Override enforcement
./WebcatCLI.py --no-override ~/my-java-project
```

---

## Running the Built-in Test Suite

We include **`test_webcatcli.sh`**, a bash script that:

1. **Creates** a temporary Java project with both “good” and “bad” example files.
2. **Exercises** all CLI flags (`--no-javadoc`, `--no-override`, coverage flags, etc.).
3. **Validates** exit codes and expected output.

### To run it:

```bash
# From the directory containing WebcatCLI.py:
chmod +x test_webcatcli.sh
./test_webcatcli.sh
```

* A successful run ends with:

  ```
  🎉 All tests passed!
  ```

* If any check fails, the script will stop and print an error message pointing to the failed scenario.

Feel free to inspect or extend `test_webcatcli.sh` to cover additional edge cases in your workflow.

