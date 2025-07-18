# WebcatCLI

## Version : 1.1.2

**WebcatCLI** is a self-contained Python tool that performs Web-CAT-style pre-submission checks on your Java projects:

- **Style & Formatting**  
- **Javadoc & Annotations**  
- **Testing Conventions**  
- **Build & Coverage**  
- **Cleanup & Reporting**

---

## Table of Contents

1. [Overview](#overview)  
2. [Features](#features)  
3. [Prerequisites](#prerequisites)  
4. [Installation](#installation)  
5. [Directory Layout](#directory-layout)  
6. [Quick Start](#quick-start)  
7. [CLI Options](#cli-options)  
8. [Rule Matrix](#rule-matrix)  
9. [Testing](#testing)  
10. [Contributing](#contributing)  
11. [License](#license)  

---

## Overview

WebcatCLI automates style checks, Javadoc validation, test execution, and coverage enforcement **before** you submit your code to a grading/CI system. It:

- Generates a minimal `pom.xml` (JUnit 4 & JaCoCo) on the fly  
- Runs `mvn clean verify` (when `--run-tests` is used)  
- Parses JUnit test XML into a friendly tree  
- Enforces 100% JaCoCo method & branch coverage  
- Tracks and cleans up all generated artifacts  

---

## Features

- **Style & Formatting**  
  - Indentation rules (spaces vs. tabs, width)  
  - Line-length limits  
  - Single public class per file  
  - Static-field usage checks  
  - Empty / unused-method detection  

- **Javadoc & Annotations**  
  - Require Javadoc on classes & methods  
  - Enforce `@author` / `@version` tags  
  - Require `@Override` on overridden methods  
  - Validate `@param` / `@return` tags  

- **Testing & Coverage**  
  - `--run-tests` → `mvn clean verify`  
  - Tree-view of JUnit results with ✅/❌/⏭️ icons  
  - Coverage summary and gap-tree from JaCoCo XML  
  - `--enable-cli-report` to regenerate XML via `jacococli.jar`  

- **Cleanup & Reporting**  
  - Automatic removal of `pom.xml`, `target/`, downloaded JARs  
  - `--no-cleanup` to preserve everything  
  - New `--cleanup` to force cleanup even in debug mode  
  - Ctrl-C / SIGTERM handler prints a message and cleans up  

---

## Prerequisites

- **Python 3.6+**  
- **Java 8+** & **Maven** (only for `--run-tests`)  
- Unix-style shell (for bundled `test_webcatcli.sh`)  
    - Legacy - not needed.  

---

## Installation

```bash
git clone https://github.com/your-org/WebcatCLI.git
cd WebcatCLI
chmod +x WebcatCLI.py
# (optional) add to PATH:
export PATH="$PATH:$(pwd)"
```

---

## Directory Layout

```txt
WebcatCLI/
├── WebcatCLI.py
├── README.md
├── CHANGELOG.md
├── templates/
│   ├── CS1114.rules.json
│   └── CS2114.rules.json
└── tests/                   ← (not included in pip (future) or GH releases currently (as of 1.1.2).)
    └── test_webcatcli.sh    ← legacy test harness
```

> **Note:** the `tests/` folder is **not** shipped in the packaged release; it lives in the repo for CI and local development.

---

## Quick Start

Run style & test checks:

```bash
./WebcatCLI.py --run-tests /path/to/my-java-project
```

Read a single file from stdin:

```bash
cat Foo.java | ./WebcatCLI.py
```

---

## CLI Options

| Flag                    | Description                                                        |
| ----------------------- | ------------------------------------------------------------------ |
| `-p, --profile <name>`  | Choose `templates/<name>.rules.json` (default: CS2114)             |
| `--max-line-length <N>` | Override maximum characters per line (`-1` to disable)             |
| `--no-javadoc`          | Skip **all** Javadoc presence checks                               |
| `--no-author`           | Skip `@author` tag check                                           |
| `--no-version`          | Skip `@version` tag check                                          |
| `--allow-globals`       | Skip static-field usage checks                                     |
| `--allow-empty`         | Allow empty method bodies                                          |
| `--allow-unused`        | Allow unused private methods                                       |
| `--no-annotations`      | Skip checking for `@Test` annotations                              |
| `--no-delta`            | Don’t require a delta in `assertEquals`                            |
| `--no-method-cov`       | Disable 100% method coverage enforcement                           |
| `--no-branch-cov`       | Disable 100% branch coverage enforcement                           |
| `--no-override`         | Don’t enforce `@Override` on overridden methods                    |
| `--run-tests`           | After style/test, run `mvn clean verify` and parse coverage        |
| `--run-main`            | After tests (and coverage), detect & run any `main()` method       |
| `--enable-cli-report`   | Download/run `jacococli.jar` to regenerate XML before parsing gaps |
| `--no-cleanup`          | Preserve generated files & directories on exit                     |
| `--cleanup`             | Force cleanup even in debug mode (overrides `--no-cleanup`)        |
| `-h, --help`            | Show usage and exit                                                |
| `--version`             | Print version (`__version__`) and exit                             |

---

## Rule Matrix

| Rule                                 |        Default        | Configurable | Change via                          |
| ------------------------------------ | :-------------------: | :----------: | ----------------------------------- |
| **Indentation: spaces per indent**   |        4 spaces       |      Yes     | JSON template / `--max-line-length` |
| **Use spaces (no tabs)**             |           ✔️          |      Yes     | JSON template                       |
| **Max line length**                  |        80 chars       |      Yes     | `--max-line-length`, JSON           |
| **Javadoc required (class/method)**  |           ✔️          |      Yes     | `--no-javadoc`, JSON                |
| **`@author` required**               |           ✔️          |      Yes     | `--no-author`, JSON                 |
| **`@version` required**              |           ✔️          |      Yes     | `--no-version`, JSON                |
| **One public class/file**            |          ✔️           |     Yes      | JSON                                |
| **Static-field usage**               | ✔️ (abiity to change) |     Yes      | `--allow-globals`, JSON             |
| **Empty-method detection**           |          ✔️           |     Yes      | `--allow-empty`, JSON               |
| **Unused-private-method detection**  |           ✔️          |      Yes     | `--allow-unused`, JSON              |
| **`@Override` enforcement**          |           ✔️          |      Yes     | `--no-override`, JSON               |
| **Package Javadoc (`@package`)**     |           ✔️          |      Yes     | `--no-package-annotation`, JSON     |
| **Require preceding `@package` tag** |           ❌           |      Yes     | `--no-package-javadoc`, JSON        |
| **Test prefix**                      |         `test`        |      Yes     | JSON                                |
| **`@Test` annotation required**      |           ❌           |      Yes     | `--no-annotations`, JSON            |
| **Delta in `assertEquals`**          |           ✔️          |      Yes     | `--no-delta`, JSON                  |
| **100% method coverage**             |           ✔️          |      Yes     | `--no-method-cov`, JSON             |
| **100% branch coverage**             |           ✔️          |      Yes     | `--no-branch-cov`, JSON             |

---

## Testing

I’ve moved the old `test_webcatcli.sh` into `tests/` for historical coverage. It:

1. Creates minimal Java projects (good & bad cases).
2. Verifies that every flag behaves as expected.
3. Ensures legacy behavior never regresses.

> **Note:** the `tests/` folder is **not** part of the release tar—developers can clone the repo and run:
> **Note**: The Test Program Does Not Respect or Consider the JSON configurations when creating and applying these tests. Needs to be updated for next release.

```bash
cd tests
chmod +x test_webcatcli.sh
./test_webcatcli.sh
```
