#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEBCAT="$ROOT/bin/webcat"
tmp=""
JAVAC_BIN="${JAVAC_BIN:-}"
JAR_BIN="${JAR_BIN:-}"

if [ -z "$JAVAC_BIN" ]; then
  if [ -x /opt/homebrew/opt/openjdk@21/bin/javac ]; then
    JAVAC_BIN=/opt/homebrew/opt/openjdk@21/bin/javac
  else
    JAVAC_BIN="$(command -v javac || true)"
  fi
fi

if [ -z "$JAR_BIN" ]; then
  if [ -x /opt/homebrew/opt/openjdk@21/bin/jar ]; then
    JAR_BIN=/opt/homebrew/opt/openjdk@21/bin/jar
  else
    JAR_BIN="$(command -v jar || true)"
  fi
fi

cleanup() {
  if [ -n "$tmp" ]; then
    rm -rf "$tmp"
  fi
  rm -f /tmp/webcat-missing-profile.out
}
trap cleanup EXIT

pass() {
  printf 'PASS %s\n' "$1"
}

fail() {
  printf 'FAIL %s\n' "$1" >&2
  exit 1
}

[ -n "$JAVAC_BIN" ] && [ -x "$JAVAC_BIN" ] || fail "javac is required for cs3114 fixture"
[ -n "$JAR_BIN" ] && [ -x "$JAR_BIN" ] || fail "jar is required for cs3114 fixture"

contains() {
  haystack="$1"
  needle="$2"
  printf '%s' "$haystack" | grep -F "$needle" >/dev/null 2>&1
}

out="$("$WEBCAT" doctor)"
contains "$out" '"schema":1' || fail "doctor emits schema"
contains "$out" '"command":"doctor"' || fail "doctor emits command"
contains "$out" '"profile":"cs3114"' || fail "doctor defaults to cs3114"
pass "doctor default profile"

out="$("$WEBCAT" --profile cs2505 doctor)"
contains "$out" '"profile":"cs2505"' || fail "doctor honors profile override"
contains "$out" 'CS2505 VTWebCatCLI profile' || fail "doctor loads cs2505 profile"
contains "$out" '"test":"classic_maven_jacoco"' || fail "cs2505 uses classic Maven/Jacoco backend"
contains "$out" '"mutation":"none"' || fail "cs2505 has no mutation backend"
contains "$out" '"commands":["test","doctor"]' || fail "cs2505 command capabilities"
pass "doctor cs2505 profile"

out="$("$WEBCAT" --profile cs3114 doctor)"
contains "$out" '"profile":"cs3114"' || fail "doctor honors cs3114 override"
contains "$out" '"test":"direct_junit"' || fail "cs3114 uses direct JUnit backend"
contains "$out" '"mutation":"pit168"' || fail "cs3114 uses PIT backend"
contains "$out" '"commands":["test","mutate","doctor"]' || fail "cs3114 command capabilities"
pass "doctor cs3114 profile"

tmp="${TMPDIR:-/tmp}/webcat-test-$$"
cleanup
tmp="${TMPDIR:-/tmp}/webcat-test-$$"
mkdir -p "$tmp/sub/dir"
tmp="$(cd "$tmp" && pwd -P)"
cat > "$tmp/.webcat.toml" <<'EOF'
profile = "cs2505"
src = "source"
EOF

out="$(cd "$tmp/sub/dir" && "$WEBCAT" doctor)"
contains "$out" "$tmp/.webcat.toml" || fail "doctor finds walk-up config"
contains "$out" '"profile":"cs2505"' || fail "doctor uses config profile"
pass "config walk-up"

cleanup
tmp="${TMPDIR:-/tmp}/webcat-test-$$"
mkdir -p "$tmp/src"
cat > "$tmp/.webcat.toml" <<'EOF'
profile = "cs2505"
src = "src"
EOF
cat > "$tmp/src/Good.java" <<'EOF'
/**
 * @author Tester
 * @version 1.0
 */
public class Good {
    /**
     * Example method.
     */
    public void foo() {
        System.out.println("ok");
    }
}
EOF
out="$(cd "$tmp" && WEBCAT_CLASSIC_TIMEOUT=1 "$WEBCAT" test)"
contains "$out" '"profile":"cs2505"' || fail "cs2505 classic test emits profile"
contains "$out" '"backend":"classic_vtwebcatcli"' || fail "cs2505 test uses classic backend"
pass "cs2505 classic wrapper"

if "$WEBCAT" --profile cs2505 mutate >/tmp/webcat-cs2505-mutate.out 2>/dev/null; then
  fail "cs2505 mutate should be unsupported"
fi
contains "$(cat /tmp/webcat-cs2505-mutate.out)" '"kind":"unsupported_profile_command"' || fail "cs2505 mutate emits unsupported JSON"
rm -f /tmp/webcat-cs2505-mutate.out
pass "cs2505 mutation unsupported"

cleanup
tmp="${TMPDIR:-/tmp}/webcat-test-$$"
mkdir -p "$tmp/fake-junit/org/junit/runner" "$tmp/fake-junit/org/junit" "$tmp/src"
cat > "$tmp/fake-junit/org/junit/Test.java" <<'EOF'
package org.junit;
public @interface Test {}
EOF
cat > "$tmp/fake-junit/org/junit/Assert.java" <<'EOF'
package org.junit;
public class Assert {
    public static void assertTrue(boolean value) {
        if (!value) {
            throw new AssertionError();
        }
    }
}
EOF
cat > "$tmp/fake-junit/org/junit/runner/JUnitCore.java" <<'EOF'
package org.junit.runner;
public class JUnitCore {
    public static void main(String[] args) {
        System.out.println("OK (" + args.length + " tests)");
    }
}
EOF
"$JAVAC_BIN" -d "$tmp/fake-junit-classes" $(find "$tmp/fake-junit" -name '*.java' -type f)
"$JAR_BIN" cf "$tmp/student.jar" -C "$tmp/fake-junit-classes" .
cat > "$tmp/src/AlphaTest.java" <<'EOF'
import org.junit.Test;
import static org.junit.Assert.*;
public class AlphaTest {
    @Test
    public void passes() {
        assertTrue(true);
    }
}
EOF
cat > "$tmp/src/BetaTest.java" <<'EOF'
import org.junit.Test;
public class BetaTest {
    @Test
    public void alsoPasses() {
    }
}
EOF
cat > "$tmp/.webcat.toml" <<EOF
profile = "cs3114"
src = "src"
student_jar = "$tmp/student.jar"
javac_bin = "$JAVAC_BIN"
target_tests = "AlphaTest,BetaTest"
EOF
out="$(cd "$tmp" && "$WEBCAT" test)"
contains "$out" '"command":"test"' || fail "cs3114 fixture emits test command"
contains "$out" '"ok":true' || fail "cs3114 fixture passes"
contains "$out" '"total":2' || fail "cs3114 fixture runs comma-separated test classes"
contains "$out" '"failed":0' || fail "cs3114 fixture has no failures"
pass "cs3114 direct junit fixture"

if "$WEBCAT" --profile missing doctor >/tmp/webcat-missing-profile.out 2>/dev/null; then
  fail "unknown profile should fail"
fi
contains "$(cat /tmp/webcat-missing-profile.out)" '"kind":"unknown_profile"' || fail "unknown profile emits JSON error"
pass "unknown profile failure"
