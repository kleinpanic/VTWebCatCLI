#!/usr/bin/env bash

cs2505_test() {
  root="$(project_root)"
  output_file="$root/.webcat-build/legacy-cs2505.out"
  mkdir -p "$root/.webcat-build"

  python_bin="${PYTHON:-python3}"
  legacy_cli="$ROOT_DIR/legacy/VTWebCatCLI/WebcatCLI.py"
  legacy_profile="CS2114"
  legacy_timeout="${WEBCAT_LEGACY_TIMEOUT:-45}"

  if [ ! -f "$legacy_cli" ]; then
    json_error "test" "missing_legacy_cli" "legacy VTWebCatCLI import not found" "Check legacy/VTWebCatCLI."
    return 1
  fi

  if [ -n "$PROFILE_LEGACY_RULES" ]; then
    legacy_profile="$(basename "$PROFILE_LEGACY_RULES" .rules.json)"
  fi

  "$python_bin" "$ROOT_DIR/lib/run_timeout.py" "$legacy_timeout" "$python_bin" "$legacy_cli" --profile "$legacy_profile" --run-tests "$root" >"$output_file" 2>&1
  status="$?"

  if [ "$status" -eq 124 ]; then
    printf '%s\n' "legacy VTWebCatCLI run timed out after $legacy_timeout seconds" >> "$output_file"
  fi
  json_legacy_result "$WEBCAT_PROFILE" "test" "$status" "$output_file"
  return 0
}
