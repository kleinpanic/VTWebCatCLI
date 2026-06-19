#!/usr/bin/env bash

cs2505_test() {
  root="$(project_root)"
  output_file="$root/.webcat-build/classic-cs2505.out"
  mkdir -p "$root/.webcat-build"

  python_bin="${PYTHON:-python3}"
  classic_cli="$ROOT_DIR/vtwebcatcli/classic/WebcatCLI.py"
  classic_profile="CS2114"
  classic_timeout="${WEBCAT_CLASSIC_TIMEOUT:-${WEBCAT_LEGACY_TIMEOUT:-45}}"

  if [ ! -f "$classic_cli" ]; then
    json_error "test" "missing_classic_cli" "classic VTWebCatCLI engine not found" "Check vtwebcatcli/classic."
    return 1
  fi

  if [ -n "$PROFILE_CLASSIC_RULES" ]; then
    classic_profile="$(basename "$PROFILE_CLASSIC_RULES" .rules.json)"
  fi

  "$python_bin" "$ROOT_DIR/lib/run_timeout.py" "$classic_timeout" "$python_bin" "$classic_cli" --profile "$classic_profile" --run-tests "$root" >"$output_file" 2>&1
  status="$?"

  if [ "$status" -eq 124 ]; then
    printf '%s\n' "classic VTWebCatCLI run timed out after $classic_timeout seconds" >> "$output_file"
  fi
  json_classic_result "$WEBCAT_PROFILE" "test" "$status" "$output_file"
  return 0
}
