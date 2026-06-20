#!/usr/bin/env bash

project_root() {
  if [ -n "$WEBCAT_CONFIG_PATH" ]; then
    dirname "$WEBCAT_CONFIG_PATH"
  else
    pwd
  fi
}

abs_path() {
  p="$1"
  root="$2"
  case "$p" in
    /*) printf '%s\n' "$p" ;;
    *) printf '%s/%s\n' "$root" "$p" ;;
  esac
}

cs3114_java_bin() {
  if [ -n "$WEBCAT_JAVA_BIN" ]; then
    printf '%s\n' "$WEBCAT_JAVA_BIN"
  elif [ -x /opt/homebrew/opt/openjdk@21/bin/java ]; then
    printf '%s\n' /opt/homebrew/opt/openjdk@21/bin/java
  else
    command -v java 2>/dev/null || true
  fi
}

cs3114_javac_bin() {
  if [ -n "$WEBCAT_JAVAC_BIN" ]; then
    printf '%s\n' "$WEBCAT_JAVAC_BIN"
  elif [ -x /opt/homebrew/opt/openjdk@21/bin/javac ]; then
    printf '%s\n' /opt/homebrew/opt/openjdk@21/bin/javac
  else
    command -v javac 2>/dev/null || true
  fi
}

cs3114_class_names() {
  src_dir="$1"
  suffix="$2"
  find "$src_dir" -name "*$suffix.java" -type f |
    sed "s#^$src_dir/##; s#/#.#g; s#\\.java\$##" |
    paste -sd, -
}

cs3114_compile() {
  root="$(project_root)"
  src_dir="$(abs_path "$WEBCAT_SRC" "$root")"
  build_dir="$root/.webcat-build/classes"
  student_jar="$(abs_path "${WEBCAT_STUDENT_JAR:-lib/student.jar}" "$root")"
  junit_jar="$(abs_path "$WEBCAT_JUNIT_JAR" "$root")"
  hamcrest_jar="$(abs_path "$WEBCAT_HAMCREST_JAR" "$root")"
  javac_bin="$(cs3114_javac_bin)"

  if [ ! -d "$src_dir" ]; then
    json_error "$1" "missing_src" "source directory not found: $src_dir" "Set src in .webcat.toml."
    return 1
  fi
  if [ ! -f "$student_jar" ]; then
    json_error "$1" "missing_jar" "student.jar not found: $student_jar" "Set student_jar in .webcat.toml."
    return 1
  fi
  if [ ! -x "$javac_bin" ]; then
    json_error "$1" "missing_tool" "javac not executable: $javac_bin" "Set javac_bin in .webcat.toml."
    return 1
  fi

  rm -rf "$build_dir"
  mkdir -p "$build_dir"
  find "$src_dir" -name '*.java' -type f |
    sed 's/\\/\\\\/g; s/"/\\"/g; s/^/"/; s/$/"/' > "$root/.webcat-build/sources.txt"

  cp_value="$student_jar"
  [ -n "$junit_jar" ] && cp_value="$cp_value:$junit_jar"
  [ -n "$hamcrest_jar" ] && cp_value="$cp_value:$hamcrest_jar"

  "$javac_bin" -cp "$cp_value" -d "$build_dir" --release "${PROFILE_COMPILE_RELEASE:-11}" @"$root/.webcat-build/sources.txt"
}

cs3114_test() {
  if ! cs3114_compile test >/tmp/webcat-compile.out 2>/tmp/webcat-compile.err; then
    json_error "test" "compile_failed" "$(cat /tmp/webcat-compile.err)" "Fix compile errors first."
    return 1
  fi

  root="$(project_root)"
  build_dir="$root/.webcat-build/classes"
  student_jar="$(abs_path "${WEBCAT_STUDENT_JAR:-lib/student.jar}" "$root")"
  java_bin="$(cs3114_java_bin)"
  output_file="$root/.webcat-build/junit.out"
  target_tests="$WEBCAT_TARGET_TESTS"
  [ -n "$target_tests" ] || target_tests="$(cs3114_class_names "$(abs_path "$WEBCAT_SRC" "$root")" Test)"

  if [ ! -x "$java_bin" ]; then
    json_error "test" "missing_tool" "java not executable: $java_bin" "Set java_bin in .webcat.toml."
    return 1
  fi

  old_ifs="$IFS"
  IFS=','
  set -- $target_tests
  IFS="$old_ifs"

  "$java_bin" -Djava.security.manager=allow -cp "$build_dir:$student_jar" org.junit.runner.JUnitCore "$@" >"$output_file" 2>&1
  status="$?"

  if grep -q '^OK (' "$output_file"; then
    total="$(sed -n 's/^OK (\([0-9][0-9]*\) tests*)/\1/p; s/^OK (\([0-9][0-9]*\) test)/\1/p' "$output_file" | tail -1)"
    [ -n "$total" ] || total=0
    failed=0
  else
    total="$(sed -n 's/^Tests run: \([0-9][0-9]*\),.*$/\1/p' "$output_file" | tail -1)"
    failed="$(sed -n 's/^Tests run: [0-9][0-9]*,  Failures: \([0-9][0-9]*\),.*$/\1/p' "$output_file" | tail -1)"
    [ -n "$total" ] || total=0
    [ -n "$failed" ] || failed=1
  fi

  if [ "$total" -eq 0 ]; then
    json_error "test" "zero_tests" "JUnit ran zero tests" "Check target_tests and test class names."
    return 2
  fi

  json_test_result "$WEBCAT_PROFILE" "$total" "$failed" "$output_file"
  return 0
}

cs3114_mutate() {
  if ! cs3114_compile mutate >/tmp/webcat-compile.out 2>/tmp/webcat-compile.err; then
    json_error "mutate" "compile_failed" "$(cat /tmp/webcat-compile.err)" "Fix compile errors first."
    return 1
  fi

  root="$(project_root)"
  build_dir="$root/.webcat-build/classes"
  src_dir="$(abs_path "$WEBCAT_SRC" "$root")"
  student_jar="$(abs_path "${WEBCAT_STUDENT_JAR:-lib/student.jar}" "$root")"
  junit_jar="$(abs_path "$WEBCAT_JUNIT_JAR" "$root")"
  hamcrest_jar="$(abs_path "$WEBCAT_HAMCREST_JAR" "$root")"
  pit_dir="$(abs_path "$WEBCAT_PIT_DIR" "$root")"
  java_bin="$(cs3114_java_bin)"
  report_dir="$root/.webcat-pit-reports"
  csv_file="$report_dir/mutations.csv"
  target_classes="$WEBCAT_TARGET_CLASSES"
  target_tests="$WEBCAT_TARGET_TESTS"
  [ -n "$target_classes" ] || target_classes="$(find "$src_dir" -name '*.java' ! -name '*Test.java' -type f | sed "s#^$src_dir/##; s#/#.#g; s#\\.java\$##" | paste -sd, -)"
  [ -n "$target_tests" ] || target_tests="$(cs3114_class_names "$src_dir" Test)"

  for jar_name in pitest-command-line.jar pitest.jar pitest-entry.jar pitest-html-report.jar; do
    if [ ! -f "$pit_dir/$jar_name" ]; then
      json_error "mutate" "missing_jar" "PIT jar missing: $pit_dir/$jar_name" "Set pit_dir in .webcat.toml."
      return 1
    fi
  done
  if [ ! -f "$junit_jar" ] || [ ! -f "$hamcrest_jar" ]; then
    json_error "mutate" "missing_jar" "JUnit/Hamcrest jar missing" "Set junit_jar and hamcrest_jar in .webcat.toml."
    return 1
  fi

  rm -rf "$report_dir"
  "$java_bin" -Djava.security.manager=allow \
    -cp "$pit_dir/pitest-command-line.jar:$pit_dir/pitest.jar:$pit_dir/pitest-entry.jar:$pit_dir/pitest-html-report.jar:$junit_jar:$hamcrest_jar:$student_jar:$build_dir" \
    org.pitest.mutationtest.commandline.MutationCoverageReport \
    --reportDir "$report_dir" \
    --targetClasses "$target_classes" \
    --targetTests "$target_tests" \
    --sourceDirs "$src_dir" \
    --classPath "$build_dir,$student_jar,$junit_jar,$hamcrest_jar" \
    --outputFormats CSV,HTML \
    --mutators "$PROFILE_PIT_MUTATORS" \
    --timestampedReports=false >/tmp/webcat-pit.out 2>/tmp/webcat-pit.err

  if [ ! -f "$csv_file" ]; then
    json_error "mutate" "pit_failed" "$(cat /tmp/webcat-pit.err)" "Check PIT jars, target classes, and target tests."
    return 1
  fi

  total="$(awk 'END { print NR }' "$csv_file")"
  killed="$(awk -F, '$6 == "KILLED" { n++ } END { print n + 0 }' "$csv_file")"
  survived="$(awk -F, '$6 != "KILLED" { n++ } END { print n + 0 }' "$csv_file")"
  json_mutation_result "$WEBCAT_PROFILE" "$total" "$killed" "$survived" "$csv_file"
}

cs3114_json_file_array() {
  file="$1"
  first=true
  printf '['
  if [ -f "$file" ]; then
    while IFS= read -r item; do
      if [ -n "$item" ]; then
        if [ "$first" = "true" ]; then
          first=false
        else
          printf ','
        fi
        json_string "$item"
      fi
    done < "$file"
  fi
  printf ']'
}

cs3114_source_report() {
  root="$(project_root)"
  src_dir="$(abs_path "$WEBCAT_SRC" "$root")"
  submission_root="$(dirname "$src_dir")"
  tmp_dir="$root/.webcat-build/report"
  mkdir -p "$tmp_dir"
  generated_file="$tmp_dir/generated.txt"
  nested_file="$tmp_dir/nested-java.txt"
  forbidden_file="$tmp_dir/forbidden.txt"
  issue_file="$tmp_dir/issues.txt"
  : > "$generated_file"
  : > "$nested_file"
  : > "$forbidden_file"
  : > "$issue_file"

  if [ -d "$submission_root" ]; then
    find "$submission_root" \( -path '*/bin/*' -o -name '*.class' \) -type f |
      sed "s#^$submission_root/##" | sort > "$generated_file"
  fi

  if [ -d "$src_dir" ]; then
    find "$src_dir" -mindepth 2 -name '*.java' -type f |
      sed "s#^$src_dir/##" | sort > "$nested_file"
    grep -RInE 'ArrayList|HashMap|Vector|LinkedList|TreeMap|TreeSet|HashSet|Map<|List<|java\.util|System\.out' "$src_dir" --include='*.java' 2>/dev/null |
      sed "s#^$src_dir/##" > "$forbidden_file" || true
  fi

  [ -s "$generated_file" ] && printf '%s\n' "generated_artifacts: remove local build outputs from the submission tree" >> "$issue_file"
  [ -s "$nested_file" ] && printf '%s\n' "nested_source: CS3114 expects a flat src directory" >> "$issue_file"
  [ -s "$forbidden_file" ] && printf '%s\n' "forbidden_structures: implementation source references off-limits APIs or System.out" >> "$issue_file"

  printf '{"root":'
  json_string "$submission_root"
  printf ',"src":'
  json_string "$src_dir"
  printf ',"flat_src":'
  if [ -s "$nested_file" ]; then json_bool false; else json_bool true; fi
  printf ',"generated_artifacts":'
  cs3114_json_file_array "$generated_file"
  printf ',"nested_source_files":'
  cs3114_json_file_array "$nested_file"
  printf ',"forbidden_hits":'
  cs3114_json_file_array "$forbidden_file"
  printf ',"source_files":['

  first=true
  if [ -d "$src_dir" ]; then
    find "$src_dir" -maxdepth 1 -name '*.java' -type f | sort |
    while IFS= read -r src_file; do
      rel="$(basename "$src_file")"
      lines="$(wc -l < "$src_file" | tr -d ' ')"
      is_test=false
      case "$rel" in
        *Test.java) is_test=true ;;
      esac
      over_limit=false
      if [ "$is_test" = "false" ] && [ "$lines" -gt 600 ]; then
        over_limit=true
        printf '%s\n' "source_line_limit: $rel has $lines lines, over 600" >> "$issue_file"
      fi
      pledge=false
      if grep -q 'On my honor:' "$src_file"; then
        pledge=true
      fi
      if [ "$first" = "true" ]; then
        first=false
      else
        printf ','
      fi
      printf '{"path":'
      json_string "$rel"
      printf ',"lines":%s,"is_test":' "$lines"
      json_bool "$is_test"
      printf ',"over_source_limit":'
      json_bool "$over_limit"
      printf ',"has_pledge":'
      json_bool "$pledge"
      printf '}'
    done
  fi

  printf '],"pledge_present":'
  if [ -d "$src_dir" ] && grep -RIl 'On my honor:' "$src_dir" --include='*.java' >/dev/null 2>&1; then
    json_bool true
  else
    json_bool false
    printf '%s\n' "pledge_missing: no pledge text found in source files" >> "$issue_file"
  fi
  printf ',"issues":'
  cs3114_json_file_array "$issue_file"
  printf '}'
}

cs3114_report() {
  test_json="$(cs3114_test)"
  test_status="$?"

  if [ "$test_status" -eq 0 ]; then
    mutation_json="$(cs3114_mutate)"
    mutation_status="$?"
  else
    mutation_json='null'
    mutation_status=2
  fi

  ok=true
  [ "$test_status" -ne 0 ] && ok=false
  [ "$mutation_status" -ne 0 ] && ok=false

  printf '{"schema":1,"command":"report","ok":'
  json_bool "$ok"
  printf ',"profile":'
  json_string "$WEBCAT_PROFILE"
  printf ',"local":{"test":%s,"mutation":%s,"submission":' "$test_json" "$mutation_json"
  cs3114_source_report
  printf '}'
  printf ',"webcat_parity":{'
  printf '"matches":["java_compile","student_junit_tests","local_pit_mutation","local_submission_shape_checks","local_source_file_summary"],'
  printf '"partial":["per_file_mutation_targets","source_rendered_report","style_shape_checks"],'
  printf '"unsupported":["assignment_metadata","official_style_score","design_readability_score","hidden_reference_correctness","problem_coverage","valid_test_percentage","official_final_score","early_bonus","authenticated_submit"],'
  printf '"note":'
  json_string "This is a local preflight report, not the official CS3114 Web-CAT report."
  printf '}}\n'
}
