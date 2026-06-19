#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
tmp="${TMPDIR:-/tmp}/vtwebcatcli-classic-run-tests-$$"

cleanup() {
  rm -rf "$tmp"
}
trap cleanup EXIT

rm -rf "$tmp"
mkdir -p "$tmp/src"

cat > "$tmp/src/Calc.java" <<'EOF'
/**
 * @author Tester
 * @version 1.0
 */
public class Calc {
    /**
     * Adds two numbers.
     *
     * @param a first number
     * @param b second number
     * @return sum of both numbers
     */
    public int add(int a, int b) {
        return a + b;
    }
}
EOF

cat > "$tmp/src/CalcTest.java" <<'EOF'
import org.junit.Test;
import static org.junit.Assert.*;

/**
 * @author Tester
 * @version 1.0
 */
public class CalcTest {
    /**
     * Checks addition.
     */
    @Test
    public void testAdd() {
        assertEquals(5.0, new Calc().add(2, 3), 0.0);
    }
}
EOF

python3 "$ROOT/WebcatCLI.py" --run-tests "$tmp" > "$tmp/classic-run-tests.out" 2>&1

grep -F 'testAdd' "$tmp/classic-run-tests.out" >/dev/null
grep -F 'Method coverage: 100.0%' "$tmp/classic-run-tests.out" >/dev/null
grep -F 'Branch coverage: 100.0%' "$tmp/classic-run-tests.out" >/dev/null

printf 'PASS classic run-tests Maven/JUnit/JaCoCo\n'
