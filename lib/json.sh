#!/usr/bin/env bash

json_escape() {
  # Escape the small set of characters needed for JSON strings.
  awk 'BEGIN {
    s = ARGV[1]
    ARGV[1] = ""
    gsub(/\\/, "\\\\", s)
    gsub(/"/, "\\\"", s)
    gsub(/\t/, "\\t", s)
    gsub(/\r/, "\\r", s)
    gsub(/\n/, "\\n", s)
    printf "%s", s
  }' "$1"
}

json_string() {
  printf '"%s"' "$(json_escape "$1")"
}

json_null_or_string() {
  if [ -z "$1" ]; then
    printf 'null'
  else
    json_string "$1"
  fi
}

json_bool() {
  if [ "$1" = "true" ]; then
    printf 'true'
  else
    printf 'false'
  fi
}

json_csv_array() {
  csv="$1"
  first=true
  printf '['
  old_ifs="$IFS"
  IFS=','
  for item in $csv; do
    IFS="$old_ifs"
    if [ -n "$item" ]; then
      if [ "$first" = "true" ]; then
        first=false
      else
        printf ','
      fi
      json_string "$item"
    fi
    IFS=','
  done
  IFS="$old_ifs"
  printf ']'
}

json_error() {
  command_name="$1"
  kind="$2"
  message="$3"
  hint="$4"
  printf '{"schema":1,"command":'
  json_string "$command_name"
  printf ',"ok":false,"profile":'
  json_null_or_string "${WEBCAT_PROFILE:-}"
  printf ',"error":{"kind":'
  json_string "$kind"
  printf ',"message":'
  json_string "$message"
  printf ',"hint":'
  json_string "$hint"
  printf '}}\n'
}

json_unsupported() {
  command_name="$1"
  message="$2"
  json_error "$command_name" "unsupported_profile_command" "$message" "Use a command supported by this profile."
}

json_test_result() {
  profile="$1"
  total="$2"
  failed="$3"
  output_file="$4"
  passed=$((total - failed))
  ok=true
  [ "$failed" -gt 0 ] && ok=false

  printf '{"schema":1,"command":"test","ok":'
  json_bool "$ok"
  printf ',"profile":'
  json_string "$profile"
  printf ',"summary":{"total":%s,"passed":%s,"failed":%s},"failures":[],"issues":[],"raw_output":' "$total" "$passed" "$failed"
  json_string "$(cat "$output_file")"
  printf '}\n'
}

json_classic_result() {
  profile="$1"
  command_name="$2"
  status="$3"
  output_file="$4"
  ok=true
  [ "$status" -ne 0 ] && ok=false

  printf '{"schema":1,"command":'
  json_string "$command_name"
  printf ',"ok":'
  json_bool "$ok"
  printf ',"profile":'
  json_string "$profile"
  printf ',"summary":{"backend":"classic_vtwebcatcli","exit_code":%s},"failures":[],"issues":[],"raw_output":' "$status"
  json_string "$(cat "$output_file")"
  printf '}\n'
}

json_mutation_result() {
  profile="$1"
  total="$2"
  killed="$3"
  survived="$4"
  csv_file="$5"
  pct="0"
  if [ "$total" -gt 0 ]; then
    pct="$(awk "BEGIN { printf \"%.1f\", ($killed * 100) / $total }")"
  fi

  printf '{"schema":1,"command":"mutate","ok":true,"profile":'
  json_string "$profile"
  printf ',"coverage":{"killed":%s,"survived":%s,"total":%s,"pct":%s},"survivors":[' "$killed" "$survived" "$total" "$pct"

  first=true
  awk -F, '$6 != "KILLED" { print $1 "\t" $5 "\t" $3 "\t" $4 "\t" $2 "\t" $6 }' "$csv_file" |
  while IFS='	' read -r file line mutator method class_name status; do
    if [ "$first" = "true" ]; then
      first=false
    else
      printf ','
    fi
    printf '{"file":'
    json_string "$file"
    printf ',"line":%s,"mutator":' "$line"
    json_string "$mutator"
    printf ',"method":'
    json_string "$method"
    printf ',"class":'
    json_string "$class_name"
    printf ',"status":'
    json_string "$status"
    printf '}'
  done
  printf ']}\n'
}

json_doctor() {
  profile="$1"
  config_path="$2"
  java_ok="$3"
  java_path="$4"
  javac_ok="$5"
  javac_path="$6"
  profile_kind="$7"
  profile_description="$8"
  commands="$9"
  test_backend="${10}"
  style_backend="${11}"
  coverage_backend="${12}"
  mutation_backend="${13}"
  compile_release="${14}"
  required_tools="${15}"
  missing_tools="${16}"
  test_jars="${17}"
  mutation_jars="${18}"
  missing_jars="${19}"
  threshold_default="${20}"

  printf '{"schema":1,"command":"doctor","ok":true,"profile":'
  json_string "$profile"
  printf ',"config":{"path":'
  json_null_or_string "$config_path"
  printf '},"tools":{"java":{"ok":'
  json_bool "$java_ok"
  printf ',"path":'
  json_null_or_string "$java_path"
  printf '},"javac":{"ok":'
  json_bool "$javac_ok"
  printf ',"path":'
  json_null_or_string "$javac_path"
  printf '}},"profile_info":{"kind":'
  json_string "$profile_kind"
  printf ',"description":'
  json_string "$profile_description"
  printf ',"commands":'
  json_csv_array "$commands"
  printf ',"backends":{"test":'
  json_string "$test_backend"
  printf ',"style":'
  json_string "$style_backend"
  printf ',"coverage":'
  json_string "$coverage_backend"
  printf ',"mutation":'
  json_string "$mutation_backend"
  printf '},"compile_release":'
  json_string "$compile_release"
  printf ',"required_tools":'
  json_csv_array "$required_tools"
  printf ',"missing_tools":'
  json_csv_array "$missing_tools"
  printf ',"test_jars":'
  json_csv_array "$test_jars"
  printf ',"mutation_jars":'
  json_csv_array "$mutation_jars"
  printf ',"missing_jars":'
  json_csv_array "$missing_jars"
  printf ',"threshold_default":'
  json_string "$threshold_default"
  printf '}}\n'
}
