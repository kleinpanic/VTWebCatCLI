#!/usr/bin/env bash
set -euo pipefail

# ─── Colors ───────────────────────────────────────────────────────────────
GREEN="\033[32m"
RED="\033[31m"
RESET="\033[0m"

# ─── Locate python3 or python ─────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
  echo -e "${RED}Error:${RESET} python3 (or python) not found in PATH." >&2
  exit 1
fi

# ─── Helpers ──────────────────────────────────────────────────────────────
FAILED=false

expect_success() {
  local desc="$1"; shift
  printf "%-50s" "${desc}..."
  if "$@" >/dev/null 2>&1; then
    printf "${GREEN}✔ PASS${RESET}\n"
  else
    printf "${RED}✖ FAIL (unexpected)${RESET}\n"
    FAILED=true
  fi
}

expect_failure() {
  local desc="$1"; shift
  printf "%-50s" "${desc}..."
  if "$@" >/dev/null 2>&1; then
    printf "${RED}✖ PASS (unexpected success)${RESET}\n"
    FAILED=true
  else
    printf "${GREEN}✔ expected FAIL${RESET}\n"
  fi
}

# ─── Portable tempdir ─────────────────────────────────────────────────────
if TMPDIR=$(mktemp -d "${TMPDIR:-/tmp}/wc_test.XXXXXX" 2>/dev/null); then
  :
elif TMPDIR=$(mktemp -d -t wc_test 2>/dev/null); then
  :
else
  echo -e "${RED}Error:${RESET} could not create temp directory." >&2
  exit 1
fi
trap 'rm -rf "$TMPDIR"' EXIT

# ─── Locate your CLI ───────────────────────────────────────────────────────
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT/WebcatCLI.py"
if [ ! -f "$CLI" ]; then
  echo -e "${RED}Error:${RESET} Cannot find WebcatCLI.py at $CLI" >&2
  exit 1
fi

# ─── Always allow static methods (main) ───────────────────────────────────
ALLOW_GLOBALS=(--allow-globals)

# ─── Helpers to scaffold fixtures ──────────────────────────────────────────
reset_src() {
  rm -rf "$TMPDIR/src"
  mkdir -p "$TMPDIR/src"
}

write_good() {
  cat > "$TMPDIR/src/Good.java" <<'EOF'
/**
 * @author Tester
 * @version 1.0
 */
public class Good {
    /**
     * Main entry point.
     */
    public static void main(String[] args) {
        System.out.println("OK");
    }

    /**
     * Example non-empty method.
     */
    public void foo() {
        /* non-empty */
    }

    /**
     * Provide a custom toString().
     *
     * @return description of this object
     */
    @Override
    public String toString() {
        return "Good";
    }
}
EOF

  cat > "$TMPDIR/src/GoodTest.java" <<'EOF'
import org.junit.Test;
import static org.junit.Assert.*;

/**
 * @author Tester
 * @version 1.0
 * Test class for Good.
 */
public class GoodTest {
    /**
     * Verifies foo() returns correctly.
     */
    @Test
    public void testFoo() {
        assertEquals(1.0, 1.0, 0.0);
    }
}
EOF
}

write_bad() {
  cat > "$TMPDIR/src/Bad.java" <<'EOF'
/** Missing version and author */
public class Bad {
    private static int X;    // static field
    public void empty(){}    // empty method
    private int unused() { return 0; }
}
EOF

  cat > "$TMPDIR/src/BadTest.java" <<'EOF'
public class BadTest {
    public void foo() {
        assertEquals(2.5,2.5);  // missing delta and missing @Test
    }
}
EOF
}

write_sub_without_override() {
  cat > "$TMPDIR/src/Sub.java" <<'EOF'
/**
 * @author Tester
 * @version 1.0
 * Subclass of Good
 */
public class Sub extends Good {
    /**
     * Overrides toString but missing @Override annotation.
     *
     * @return description of this object
     */
    public String toString() {
        return "Sub";
    }
}
EOF
}

# ─── 1: Default profile on Good.java ──────────────────────────────────────
reset_src
write_good
expect_success "Default profile on Good" \
  "$PYTHON" "$CLI" "${ALLOW_GLOBALS[@]}" "$TMPDIR"

# ─── 2: Bad.java violations ───────────────────────────────────────────────
reset_src
write_bad
expect_failure "Bad.java violations" \
  "$PYTHON" "$CLI" "${ALLOW_GLOBALS[@]}" "$TMPDIR"

# ─── 3: Line-length enforcement ───────────────────────────────────────────
reset_src
write_good
# append one 200-character line to trigger max-length
printf '%*s\n' 200 "" | sed 's/ /X/g' >> "$TMPDIR/src/Good.java"
expect_failure "Line-length enforcement"   \
  "$PYTHON" "$CLI" "${ALLOW_GLOBALS[@]}" "$TMPDIR"
expect_success  "Disable length check"      \
  "$PYTHON" "$CLI" "${ALLOW_GLOBALS[@]}" --max-line-length -1 "$TMPDIR"

# ─── 4: Javadoc toggle ────────────────────────────────────────────────────
reset_src
write_good
expect_success "Disable Javadoc checks"     \
  "$PYTHON" "$CLI" "${ALLOW_GLOBALS[@]}" --no-javadoc "$TMPDIR"

# ─── 5: Testing toggles ───────────────────────────────────────────────────
reset_src
write_good
expect_success "Disable @Test & delta"      \
  "$PYTHON" "$CLI" "${ALLOW_GLOBALS[@]}" --no-annotations --no-delta "$TMPDIR"

# ─── 6: @Override enforcement ─────────────────────────────────────────────
reset_src
write_good
write_sub_without_override
expect_failure "Require @Override → expect FAIL" \
  "$PYTHON" "$CLI" "${ALLOW_GLOBALS[@]}" "$TMPDIR"
expect_success  "Disable @Override enforcement"  \
  "$PYTHON" "$CLI" "${ALLOW_GLOBALS[@]}" --no-override "$TMPDIR"

# ─── Summary ───────────────────────────────────────────────────────────────
if [ "$FAILED" = false ]; then
  printf "\n${GREEN}🎉 All tests passed!${RESET}\n"
  exit 0
else
  printf "\n${RED}Some tests FAILED. Review above.${RESET}\n"
  exit 1
fi
