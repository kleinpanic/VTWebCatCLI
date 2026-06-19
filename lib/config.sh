#!/usr/bin/env bash

WEBCAT_CONFIG_PATH=""
WEBCAT_SRC="src"
WEBCAT_PROFILE="cs3114"
WEBCAT_GATE="block"
WEBCAT_THRESHOLD="90"
WEBCAT_ASSIGNMENT_PATH=""
WEBCAT_STUDENT_JAR=""
WEBCAT_JUNIT_JAR=""
WEBCAT_HAMCREST_JAR=""
WEBCAT_PIT_DIR=""
WEBCAT_JAVA_BIN=""
WEBCAT_JAVAC_BIN=""
WEBCAT_TARGET_CLASSES=""
WEBCAT_TARGET_TESTS=""

config_find() {
  dir="$1"
  while :; do
    if [ -f "$dir/.webcat.toml" ]; then
      printf '%s\n' "$dir/.webcat.toml"
      return 0
    fi
    [ "$dir" = "/" ] && break
    dir="$(dirname "$dir")"
  done
  return 1
}

config_value() {
  key="$1"
  file="$2"
  sed -n "s/^[[:space:]]*$key[[:space:]]*=[[:space:]]*[\"']\\{0,1\\}\\([^\"'#]*\\)[\"']\\{0,1\\}[[:space:]]*\\(#.*\\)\\{0,1\\}$/\\1/p" "$file" | sed 's/[[:space:]]*$//' | tail -1
}

config_load() {
  start_dir="$1"
  profile_override="$2"

  if path="$(config_find "$start_dir")"; then
    WEBCAT_CONFIG_PATH="$path"

    value="$(config_value src "$path")"
    [ -n "$value" ] && WEBCAT_SRC="$value"

    value="$(config_value profile "$path")"
    [ -n "$value" ] && WEBCAT_PROFILE="$value"

    value="$(config_value gate "$path")"
    [ -n "$value" ] && WEBCAT_GATE="$value"

    value="$(config_value threshold "$path")"
    [ -n "$value" ] && WEBCAT_THRESHOLD="$value"

    value="$(config_value assignment_path "$path")"
    [ -n "$value" ] && WEBCAT_ASSIGNMENT_PATH="$value"

    value="$(config_value student_jar "$path")"
    [ -n "$value" ] && WEBCAT_STUDENT_JAR="$value"

    value="$(config_value junit_jar "$path")"
    [ -n "$value" ] && WEBCAT_JUNIT_JAR="$value"

    value="$(config_value hamcrest_jar "$path")"
    [ -n "$value" ] && WEBCAT_HAMCREST_JAR="$value"

    value="$(config_value pit_dir "$path")"
    [ -n "$value" ] && WEBCAT_PIT_DIR="$value"

    value="$(config_value java_bin "$path")"
    [ -n "$value" ] && WEBCAT_JAVA_BIN="$value"

    value="$(config_value javac_bin "$path")"
    [ -n "$value" ] && WEBCAT_JAVAC_BIN="$value"

    value="$(config_value target_classes "$path")"
    [ -n "$value" ] && WEBCAT_TARGET_CLASSES="$value"

    value="$(config_value target_tests "$path")"
    [ -n "$value" ] && WEBCAT_TARGET_TESTS="$value"
  fi

  if [ -n "$profile_override" ]; then
    WEBCAT_PROFILE="$profile_override"
  fi

  return 0
}
