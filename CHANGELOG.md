# Changelog

All the good stuff in **WebcatCLI**, from the very first drop (v1.0.0) through the current version (**v1.1.2**)

---

## [1.1.4] - 2025-07-23

### Patch and New Release
- No longer using os for system calls. Should be more robust with other OSs. Uses pathlib. Helper normalize_path() now returns a resolved `path` as a string.
- Wrapped maven invocation in a try / except command to better handle failure on edge cases I havent accounted for yet. 
- Added a new flag `--delete-modules-info` to delete the modules.info file from your project since we use maven 8 it fucks it up.
    - Did not want to hardcode some shit to ignore the file in maven's xml file because of portability. 
- Recorded paths for cleanup are now cast to `Path` before removal. Downloaded Jar paths are stored as strings of path objects.
- Replaced all print calls with logging. Calls become logging.info(), logging.debug(), or logging.warning()/error() as appropriate.
- Given the accumination of past pathces, determined new version release was warranted so the release gets updated in GH.

## [1.1.3] - 2025-07-21

### Patch
- Added more support for windows systems in the form of normalizing the path and by more indepth approach to find MVN dependencies.
- included the packaging of the student.jar

## [1.1.3] – 2025-07-18

### 🎉 What’s New
- AST-based Impossible Branch Detection
    Added new --scan-impossible-branches flag, leveraging the javalang library to parse Java source files and detect logically impossible (always true/false) branch conditions. This helps to quickly identify unreachable code paths before coverage analysis.
- **runtime-compilation im**

### ⚠️ Important Notices
- **Optional Dependency (javalang)**
    The new impossible branch detection feature requires the javalang Python library. Install it via:
```bash
pip install javalang
```
The dependency check now runs only when the --scan-impossible-branches flag is invoked, preventing unnecessary errors if the flag is not used.

### 📖 Documentation Improvements
- **Updated README.md to clearly document:**
    - New CLI option (--scan-impossible-branches)
    - The optional dependency on javalang
    - Adjusted prerequisites to clarify optional installation steps

### 🛠 Under the Hood Improvements
- **Lazy Loading of Optional Dependencies**
    Moved the import check for javalang within the conditional execution path of the --scan-impossible-branches feature, eliminating dependency warnings or errors when not using this feature.
    Improved CLI Help Messages
    Enhanced argument parser help text for new flags to ensure clarity and usability.


## [1.1.2] – 2025-07-17

### 🎉 What’s new

- **Automatic cleanup**  
  Every generated file/dir (pom.xml, `target/`, downloaded `jacococli.jar` in `lib/`) is now tracked in a `CREATED` list and removed on exit by default.
- **`--cleanup` flag**  
  Forces cleanup even in debug mode (overrides the `--no-cleanup` behavior).
- **Better debug/cleanup interplay**  
  Debug mode still implies “no cleanup” unless you explicitly pass `--cleanup`.
- **Ctrl-C / SIGTERM handling**  
  Hitting Ctrl+C or receiving SIGTERM now prints “Interrupted; cleaning up…” and runs the cleanup logic before exiting.
- **Real CLI report flow**  
  - Incorporated the optional usage of a jacococli.jar file for xml generation
  - Removed the placeholder `--list-uncovered` calls with the jacococli.jar.  
  - Added `run_jacoco_cli_report()` to re-generate the XML via `jacococli.jar` and then print the coverage-gaps tree.  
  - Updated the `--enable-cli-report` help text to match (“use jacococli.jar to regenerate XML before parsing”).
- **Enhanced XML Parsing Logic**
  - On Test Analysis and Branch / Method coverage analysis, when not 100%, a report is now shown detailing deficiciencies.
  - Finalized and Enhanced Method + Branch Coverage logic to show specifics.
  - 

### 🛠 Under the hood

- Refactored **cleanup()** into a centralized function, with a global `CREATED` list.  
- `locate_or_download_jacococli()` now adds both the JAR and its `lib/` directory to `CREATED` (when appropriate).  
- Swapped out the old `run_jacoco_list_uncovered()` and its fake `--list-uncovered` for our cleaner XML-only path.  
- Argument parsing tweaked so that `--cleanup` always wins over `--no-cleanup`.

---

## [1.1.1] = 2025-07-17

### New addition

Added @package validation and requirements when in nested sub directory. 
Added @return and @param detection within javadoc and validation. 

## [1.1.0] – 2025-07-17

### 🚀 New Features

- **Version flag (`--version`)**  
  - Added a `--version` (and `-V`) option to print the CLI version (`__version__ = "1.1.0"`) and exit immediately.  
- **Tree-style Test Results Output**  
  - After running `mvn clean verify`, XML test reports in `target/surefire-reports` are now parsed and rendered as a clear *tree* structure:  
    ```
    🧪 Test results:
    ├─ MyTestSuite
    │   ├─ testFoo ✅
    │   ├─ testBar ❌: expected 5 but was 4
    │   └─ testBaz ⏭️
    └─ OtherSuite
        └─ testQuux ✅
    ```
  - Each test case shows a pass/fail/skip icon (✅❌⏭️) and any failure/error message inline.
- **Coverage Summary Section**  
  - After tests pass and coverage goals complete, prints a formatted summary:
    ```
    📊 Coverage summary:
      🧩 Method coverage: 100.0% (22/22)
      🍃 Branch coverage: 100.0% (12/12)
    ```
- **External JAR Inclusion Indicator**  
  - In `ensure_pom()`, explicitly logs whether the external `student.jar` was found and included:
    - `🔗 Including external JAR: /path/to/student.jar`
    - `— No external JAR found at /path/to/student.jar; tests will run with JUnit only`
- **Improved Debug Prefixes & Icons**  
  - Debug messages now prefixed with `🔍 Debug:` for better visibility.  
  - Info and status lines use icons (ℹ️, ✅, ❌, ▶️, 🧪, 📊, 🔗, —) to make the console output more engaging and scannable.

### 🛠 Improvements & Enhancements

- **Refactored POM Generation**  
  - Kept all existing functionality (flat‐src setup, Surefire, JaCoCo) but cleaned up code organization.  
  - Consolidated dependency array build into `deps` list, then joined into `deps_xml`.  
- **Centralized Version Constant**  
  - Introduced `__version__` module-level constant (`1.1.0`), used for `--version` output.
- **Test Report Parsing**  
  - New helper function `parse_test_reports_tree(report_dir)` to read JUnit XML and extract test case statuses.
- **Better Exit Codes**  
  - Program exits with `sys.exit(1)` if style/test checks or Maven coverage checks fail; otherwise exits with `0`.
- **Consistent Path Handling**  
  - Ensured `~` expansion for both `--path` and `--external-jar`.  
  - Uniform use of `os.path.abspath`.

### 🐛 Bug Fixes & Consistency

- **Preserved All v1.0.0 Functionality**  
  - No existing command‐line options or behaviors were removed.  
  - All style rules, test rules, coverage enforcement, `--run-main` functionality remain intact.
- **Configuration Option Defaults**  
  - Ensured default values for rule overrides remain the same when flags like `--no-method-cov` or `--no-branch-cov` are not provided.
- **Improved Error Messaging**  
  - Clearer phrasing and use of icons in error and status lines.  
  - Better handling when `--run-tests` is used without a project path.

---

## [1.0.0] – initial release

- Baseline implementation with:
  - Style & testing rule checks (indentation, JavaDoc, `@Test`, `@Override`, etc.).
  - Automatic minimal `pom.xml` generation (JUnit4, Vintage, JUnit5, JaCoCo, build-helper).
  - `--run-tests` / `--run-main` options.
  - `--debug` verbose internal logging.
  - Coverage enforcement via JaCoCo (method & branch).
  - No fancy output formatting; linear pass/fail and coverage messages.

