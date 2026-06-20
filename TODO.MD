# TODO

## CS3114 Web-CAT Parity

Goal: make `bin/webcat --profile cs3114` a serious replacement path for the
parts of Web-CAT that can be reproduced locally, and be explicit about the
parts that require Web-CAT or instructor-owned artifacts.

- Add source listing/report generation:
    - render every submitted source file with line numbers;
    - include per-file mutation summaries;
    - include warnings for files outside the flat `src` submission shape.
- Add local score modeling:
    - show local JUnit pass percentage;
    - show local mutation percentage;
    - show threshold/gate status;
    - keep official hidden/reference/problem coverage marked as unsupported
      unless authenticated Web-CAT report data is available.
- Identify or reproduce CS3114 style/readability checks:
    - find the exact Web-CAT/checkstyle rule set if installed locally;
    - otherwise add conservative local checks for Java 11, forbidden data
      structures, source line limits, flat `src`, and required pledge text.
- Add authenticated `targets`, `submit`, and report retrieval if the CLI is
  meant to replace the Eclipse/Web-CAT submission flow.
- Calibrate local PIT target selection and jars against official reports:
    - compare local mutation totals/percentages to Web-CAT PDFs;
    - document known differences instead of treating local and official numbers
      as interchangeable.

## CS2505 Logical Coverage Improvements

The original checker can overreport branch/test issues because it cannot prove
that some paths are logically unreachable.

- Investigate SFP/JPF for advanced logical reachability analysis on branches.
- Consider alternatives like JBSE or Z3/SMT-based path feasibility checks.
- Only suppress branch issues when the path is proven infeasible, not merely
  hard to test.
- Keep this behind a profile/config flag so the classic CS2505 behavior stays
  available for users who want the original checks.

## Config file levels:
- Have class config file level for overarching requirements and flag configurations
- Have overarching config file:
    - Allow users to specify defaults, like which class config, external jar (overlap - decide), coverage thresholds, module-info settings, etc)
    - Allow users to specify mvn stuff

## Add Plugin Architecture
- Define hooks so users can drop in custom checks without modify core. 
  
## Add Parallel File Processing
- Speed up large codebase analysis. Style check is pretty fast though

## Add --fix flag
- Fix trivial style issues. 
  
## Fix Internal Test Coverage
