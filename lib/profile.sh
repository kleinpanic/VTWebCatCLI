#!/usr/bin/env bash

PROFILE_KIND=""
PROFILE_DESCRIPTION=""
PROFILE_COMMANDS=""
PROFILE_TEST_BACKEND=""
PROFILE_STYLE_BACKEND=""
PROFILE_COVERAGE_BACKEND=""
PROFILE_MUTATION_BACKEND=""
PROFILE_COMPILE_RELEASE=""
PROFILE_REQUIRED_TOOLS=""
PROFILE_TEST_JARS=""
PROFILE_MUTATION_JARS=""
PROFILE_THRESHOLD_DEFAULT=""
PROFILE_LEGACY_RULES=""
PROFILE_PIT_MUTATORS=""
PROFILE_ZERO_TEST_POLICY=""

profile_value() {
  key="$1"
  file="$2"
  sed -n "s/^$key=//p" "$file" | tail -1
}

profile_load() {
  profile="$1"
  profile_file="$ROOT_DIR/profiles/$profile/profile.conf"

  if [ ! -f "$profile_file" ]; then
    return 1
  fi

  PROFILE_KIND="$(profile_value kind "$profile_file")"
  PROFILE_DESCRIPTION="$(profile_value description "$profile_file")"
  PROFILE_COMMANDS="$(profile_value commands "$profile_file")"
  PROFILE_TEST_BACKEND="$(profile_value test_backend "$profile_file")"
  PROFILE_STYLE_BACKEND="$(profile_value style_backend "$profile_file")"
  PROFILE_COVERAGE_BACKEND="$(profile_value coverage_backend "$profile_file")"
  PROFILE_MUTATION_BACKEND="$(profile_value mutation_backend "$profile_file")"
  PROFILE_COMPILE_RELEASE="$(profile_value compile_release "$profile_file")"
  PROFILE_REQUIRED_TOOLS="$(profile_value required_tools "$profile_file")"
  PROFILE_TEST_JARS="$(profile_value test_jars "$profile_file")"
  PROFILE_MUTATION_JARS="$(profile_value mutation_jars "$profile_file")"
  PROFILE_THRESHOLD_DEFAULT="$(profile_value threshold_default "$profile_file")"
  PROFILE_LEGACY_RULES="$(profile_value legacy_rules "$profile_file")"
  PROFILE_PIT_MUTATORS="$(profile_value pit_mutators "$profile_file")"
  PROFILE_ZERO_TEST_POLICY="$(profile_value zero_test_policy "$profile_file")"

  [ -n "$PROFILE_KIND" ] || PROFILE_KIND="$profile"
  [ -n "$PROFILE_DESCRIPTION" ] || PROFILE_DESCRIPTION="$profile profile"
  return 0
}
