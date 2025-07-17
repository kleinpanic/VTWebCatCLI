# Changelog

All notable changes to **WebcatCLI** between **v1.0.0** and **v1.1.0**.

---

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

