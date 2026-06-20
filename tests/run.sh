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
contains "$out" '"commands":["test","coverage","mutate","doctor","report"]' || fail "cs3114 command capabilities"
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
mkdir -p "$tmp"
cat > "$tmp/mutations.csv" <<'EOF'
SparseMatrix.java,SparseMatrix,Mutator,rowScore,10,KILLED,MovieRaterTest
SparseMatrix.java,SparseMatrix,Mutator,rowScore,11,SURVIVED,none
SparseMatrix.java,SparseMatrix,Mutator,rowScore,12,LINES_NEEDING_BETTER_TESTING,none
SparseMatrix.java,SparseMatrix,Mutator,rowScore,13,NO_COVERAGE,none
SparseMatrix.java,SparseMatrix,Mutator,rowScore,14,TIMED_OUT,MovieRaterTest
SparseMatrix.java,SparseMatrix,Mutator,rowScore,15,RUN_ERROR,none
SparseMatrix.java,SparseMatrix,Mutator,rowScore,16,NON_VIABLE,none
SparseMatrix.java,SparseMatrix,Mutator,rowScore,17,STRANGE_STATUS,none
EOF
out="$(ROOT_DIR="$ROOT" CSV_FILE="$tmp/mutations.csv" sh -c '. "$ROOT_DIR/lib/json.sh"; json_mutation_result_from_csv cs3114 "$CSV_FILE" "SparseMatrix,MovieRaterDB" false "MovieRaterTest" false')"
contains "$out" '"killed":1' || fail "mutation parser counts killed"
contains "$out" '"survived":2' || fail "mutation parser counts survived and lines needing testing"
contains "$out" '"no_coverage":1' || fail "mutation parser counts no coverage"
contains "$out" '"timed_out":1' || fail "mutation parser counts timeouts"
contains "$out" '"run_error":1' || fail "mutation parser counts run errors"
contains "$out" '"non_viable":1' || fail "mutation parser counts non-viable mutations"
contains "$out" '"other":1' || fail "mutation parser preserves unknown PIT statuses"
contains "$out" '"undetected":7' || fail "mutation parser counts every non-killed mutation"
contains "$out" '"total":8' || fail "mutation parser counts total rows"
contains "$out" '"pct":12.5' || fail "mutation parser reports killed over total"
contains "$out" '"formula":"killed / total"' || fail "mutation parser documents percentage formula"
contains "$out" '"target_classes":["SparseMatrix","MovieRaterDB"]' || fail "mutation parser reports target classes"
contains "$out" '"target_classes_inferred":false' || fail "mutation parser reports explicit target classes"
contains "$out" '"LINES_NEEDING_BETTER_TESTING":1' || fail "mutation parser includes exact PIT status counts"
contains "$out" '"STRANGE_STATUS":1' || fail "mutation parser includes unknown status counts"
pass "cs3114 mutation CSV status parser"

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

cat >> "$tmp/.webcat.toml" <<EOF
pit_dir = "$tmp/missing-pit"
EOF
out="$(cd "$tmp" && "$WEBCAT" report)"
contains "$out" '"command":"report"' || fail "cs3114 report emits report command"
contains "$out" '"local":{"test":' || fail "cs3114 report embeds local test result"
contains "$out" '"coverage":{"schema":1,"command":"coverage","ok":false' || fail "cs3114 report embeds coverage result"
contains "$out" '"mutation":{"schema":1,"command":"mutate","ok":false' || fail "cs3114 report embeds mutation error"
contains "$out" '"submission":{"root":' || fail "cs3114 report embeds submission summary"
contains "$out" '"source_files":[' || fail "cs3114 report lists source files"
contains "$out" '"local_jacoco_coverage_uncalibrated"' || fail "cs3114 report labels JaCoCo as uncalibrated"
contains "$out" '"local_pit_mutation_uncalibrated"' || fail "cs3114 report labels PIT as uncalibrated"
contains "$out" '"unsupported":["assignment_metadata","official_style_score","design_readability_score","hidden_reference_correctness","problem_coverage","valid_test_percentage","official_final_score","early_bonus","authenticated_submit"]' || fail "cs3114 report labels Web-CAT-only fields"
pass "cs3114 report parity labels"

if "$WEBCAT" --profile missing doctor >/tmp/webcat-missing-profile.out 2>/dev/null; then
  fail "unknown profile should fail"
fi
contains "$(cat /tmp/webcat-missing-profile.out)" '"kind":"unknown_profile"' || fail "unknown profile emits JSON error"
pass "unknown profile failure"
