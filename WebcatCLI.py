#!/usr/bin/env python3
"""
WebcatCLI.py

A self-contained WebCAT-style pre-submission checker:
  - Coding/Styling rules
  - Correctness/Testing rules
  - Auto-generates a minimal Maven pom.xml (with JUnit, optional student.jar & JaCoCo)
  - Runs `mvn clean verify` to compile, test, and produce coverage
  - Parses JaCoCo XML for 100% method & branch coverage
  - Enforces @Override on overridden methods (configurable)
  - Optional `--run-main` to invoke your main() after tests
  - Optional `--external-jar` to point at a custom student.jar
  - Optional `--debug` to print verbose internal state
  - `--version` to show current CLI version
"""

import argparse, json, os, re, subprocess, sys, tempfile, xml.etree.ElementTree as ET

__version__ = "1.1.0"
DEBUG = False

def load_rules(profile):
    path = os.path.join(os.path.dirname(__file__), 'templates',
                        f'{profile}.rules.json')
    if not os.path.isfile(path):
        sys.exit(f'Error: profile "{profile}" not found')
    return json.load(open(path, encoding='utf-8'))

def override_rules(rules, args):
    # style overrides
    if args.max_line_length is not None:
        rules['style']['max_line_length'] = args.max_line_length
    if args.no_javadoc:
        rules['style']['javadoc_required'] = False
    if args.no_author:
        rules['style']['javadoc_require_author'] = False
    if args.no_version:
        rules['style']['javadoc_require_version'] = False
    if args.allow_globals:
        rules['style']['disallow_global_variables'] = False
    if args.allow_empty:
        rules['style']['no_empty_methods'] = False
    if args.allow_unused:
        rules['style']['no_unused_methods'] = False
    if args.no_override:
        rules['style']['require_override'] = False

    # testing overrides
    if args.no_annotations:
        rules['testing']['annotation_required'] = False
    if args.no_delta:
        rules['testing']['require_assert_equals_delta'] = False
    if args.no_method_cov:
        rules['testing']['require_full_method_coverage'] = False
    if args.no_branch_cov:
        rules['testing']['require_full_branch_coverage'] = False

    # external-jar override
    if args.external_jar:
        rules['external_jar'] = args.external_jar

    return rules

def collect_sources(path):
    if path is None:
        tmp = tempfile.NamedTemporaryFile(delete=False,
                                          suffix='.java',
                                          mode='w',
                                          encoding='utf-8')
        tmp.write(sys.stdin.read()); tmp.close()
        return [tmp.name]
    src = os.path.join(path, 'src')
    if not os.path.isdir(src):
        sys.exit(f'Error: expected directory "{src}"')
    out = []
    for root,_,files in os.walk(src):
        for fn in files:
            if fn.endswith('.java'):
                out.append(os.path.join(root, fn))
    return out

def ensure_pom(root, rules):
    pom = os.path.join(root, 'pom.xml')
    if os.path.exists(pom):
        if DEBUG:
            print(f"Debug: pom.xml already exists at {pom}, skipping generation")
        return

    if DEBUG:
        print(f"Debug: ensure_pom called with root={root}")

    # determine external JAR
    script_dir = os.path.dirname(__file__)
    ext_jar = rules.get('external_jar') or os.path.join(script_dir, 'student.jar')
    ext_jar = os.path.abspath(ext_jar)
    has_student = os.path.isfile(ext_jar)
    if has_student:
        print(f'🔗 Including external JAR: {ext_jar}')
    else:
        print(f'— No external JAR found at {ext_jar}; tests will run with JUnit only')
    if DEBUG:
        print(f"Debug: student.jar path: {ext_jar} (exists: {has_student})")

    # assemble dependencies
    deps = []
    if has_student:
        deps.append(f'''
    <dependency>
      <groupId>edu.vt.student</groupId>
      <artifactId>student</artifactId>
      <version>1.0</version>
      <scope>system</scope>
      <systemPath>{ext_jar}</systemPath>
    </dependency>''')

    # always include JUnit 4, the Vintage engine (for Student.TestCase) and JUnit 5
    deps.append('''
    <dependency>
      <groupId>junit</groupId>
      <artifactId>junit</artifactId>
      <version>4.13.2</version>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.junit.vintage</groupId>
      <artifactId>junit-vintage-engine</artifactId>
      <version>5.7.1</version>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter-engine</artifactId>
      <version>5.7.1</version>
      <scope>test</scope>
    </dependency>''')

    deps_xml = '\n'.join(deps)
    if DEBUG:
        print("Debug: dependencies XML block:", deps_xml)

    # full POM with Surefire & JaCoCo (XML + HTML)
    content = f'''<project xmlns="http://maven.apache.org/POM/4.0.0"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                            http://maven.apache.org/xsd/maven-4.0.0.xsd">
      <modelVersion>4.0.0</modelVersion>
      <groupId>com.example</groupId>
      <artifactId>webcat-project</artifactId>
      <version>1.0-SNAPSHOT</version>
      <properties>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <maven.compiler.source>1.8</maven.compiler.source>
        <maven.compiler.target>1.8</maven.compiler.target>
      </properties>
      <dependencies>{deps_xml}
      </dependencies>
      <build>
        <plugins>

          <!-- run tests -->
          <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-surefire-plugin</artifactId>
            <version>2.22.2</version>
            <configuration>
              <useModulePath>false</useModulePath>
            </configuration>
          </plugin>

          <!-- generate coverage (XML + HTML) -->
          <plugin>
            <groupId>org.jacoco</groupId>
            <artifactId>jacoco-maven-plugin</artifactId>
            <version>0.8.5</version>
            <executions>
              <execution>
                <id>prepare-agent</id>
                <goals><goal>prepare-agent</goal></goals>
              </execution>
              <execution>
                <id>report</id>
                <phase>verify</phase>
                <goals><goal>report</goal></goals>
                <configuration>
                  <formats>
                    <format>XML</format>
                    <format>HTML</format>
                  </formats>
                </configuration>
              </execution>
            </executions>
          </plugin>

          <!-- flat src & test directories (build-helper) -->
          <plugin>
            <groupId>org.codehaus.mojo</groupId>
            <artifactId>build-helper-maven-plugin</artifactId>
            <version>3.2.0</version>
            <executions>
              <execution>
                <id>add-flat-src</id>
                <phase>generate-sources</phase>
                <goals><goal>add-source</goal></goals>
                <configuration>
                  <sources>
                    <source>src</source>
                  </sources>
                </configuration>
              </execution>
              <execution>
                <id>add-flat-test</id>
                <phase>generate-test-sources</phase>
                <goals><goal>add-test-source</goal></goals>
                <configuration>
                  <sources>
                    <source>src</source>
                  </sources>
                </configuration>
              </execution>
            </executions>
          </plugin>

        </plugins>
      </build>
    </project>'''

    with open(pom, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'ℹ️  Generated minimal pom.xml in {root}')
    if DEBUG:
        print("Debug: Generated pom.xml content:")
        print(content)

def parse_coverage(xmlpath):
    tree = ET.parse(xmlpath)
    tot = {'METHOD':(0,0),'BRANCH':(0,0)}
    for c in tree.findall('.//counter'):
        t = c.get('type')
        if t in tot:
            tot[t] = (int(c.get('missed')), int(c.get('covered')))
    return tot

def split_args(s):
    parts, cur, depth, in_str = [], '', 0, False
    qc = None
    for ch in s:
        if ch in "\"'":
            if not in_str:
                in_str, qc = True, ch
            elif qc == ch:
                in_str = False
            cur += ch; continue
        if in_str:
            cur += ch; continue
        if ch == '(':
            depth += 1; cur += ch; continue
        if ch == ')':
            depth -= 1; cur += ch; continue
        if ch == ',' and depth == 0:
            parts.append(cur.strip()); cur = ''; continue
        cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts

def check_file(path, rules):
    errs = []
    lines = open(path, encoding='utf-8').read().splitlines(keepends=True)
    text = ''.join(lines)
    s, t = rules['style'], rules['testing']

    # STYLE: indentation & tabs (skip comments/javadoc)
    in_jdoc = False
    for i, ln in enumerate(lines, 1):
        st = ln.lstrip()
        if st.startswith('/**'): in_jdoc = True
        if in_jdoc:
            if '*/' in st: in_jdoc = False
            continue
        if st.startswith('*') or st.startswith('//'):
            continue
        if s.get('no_tabs') and '\t' in ln:
            errs.append(f'Line {i}: tab found (use spaces)')
        m = re.match(r'^( +)', ln)
        if m:
            spc = s['indentation']['spaces_per_indent']
            if len(m.group(1)) % spc != 0:
                errs.append(
                  f'Line {i}: indent of {len(m.group(1))} spaces not multiple of {spc}')

    # max line length
    ml = s.get('max_line_length', -1)
    if ml > 0:
        for i, ln in enumerate(lines, 1):
            if len(ln.rstrip('\n')) > ml:
                errs.append(f'Line {i}: length {len(ln.rstrip())}>{ml}')

    # one public class per file
    if s.get('one_public_class_per_file'):
        pubs = re.findall(
          r'^\s*public\s+(?:class|interface)\s+\w+', text, re.M)
        if len(pubs) > 1:
            errs.append(f'{len(pubs)} public types in one file')

    # disallow static fields
    if s.get('disallow_global_variables'):
        for m in re.finditer(
          r'^\s*(?:public|protected|private)?\s+static\s+\w+', text, re.M):
            ln_no = text[:m.start()].count('\n')+1
            errs.append(f'Line {ln_no}: static field not allowed')

    # empty methods
    if s.get('no_empty_methods'):
        for m in re.finditer(r'\)\s*\{\s*\}', text):
            ln_no = text[:m.start()].count('\n')+1
            errs.append(f'Line {ln_no}: empty method body')

    # unused private methods
    if s.get('no_unused_methods'):
        for name in re.findall(
          r'private\s+\w+\s+(\w+)\(', text):
            rest = text[text.find(name):]
            if not re.search(r'\b'+name+r'\s*\(', rest[len(name):]):
                errs.append(f'unused private method "{name}"')

    # STYLE: javadoc on classes & methods
    if s.get('javadoc_required'):
        # classes
        for m in re.finditer(
          r'^\s*public\s+class\s+(\w+)', text, re.M):
            cn = m.group(1)
            ln_no = text[:m.start()].count('\n')+1
            idx = ln_no - 2
            while idx>=0 and (
              lines[idx].strip()=='' or lines[idx].strip().startswith('@')):
                idx-=1
            if idx<0 or not lines[idx].strip().endswith('*/'):
                errs.append(f'Line {ln_no}: missing JavaDoc for class {cn}')
        # methods
        for m in re.finditer(
          r'^\s*(public|protected)\s+\w[\w<>\[\]]*\s+(\w+)\(.*\)\s*\{',
          text, re.M):
            mn = m.group(2)
            ln_no = text[:m.start()].count('\n')+1
            if re.search(rf'public\s+class\s+{mn}\b', text):
                continue
            idx = ln_no - 2
            while idx>=0 and (
              lines[idx].strip()=='' or lines[idx].strip().startswith('@')):
                idx-=1
            if idx<0 or not lines[idx].strip().endswith('*/'):
                errs.append(f'Line {ln_no}: missing JavaDoc for method {mn}()')

    # javadoc @author/@version
    if s.get('javadoc_require_author') or s.get('javadoc_require_version'):
        blocks = re.findall(r'/\*\*([\s\S]*?)\*/', text)
        if not blocks:
            errs.append('No JavaDoc blocks')
        else:
            blk = blocks[0]
            if s.get('javadoc_require_author') and '@author' not in blk:
                errs.append('JavaDoc missing @author')
            if s.get('javadoc_require_version') and '@version' not in blk:
                errs.append('JavaDoc missing @version')

    # TESTING checks
    if path.endswith('Test.java'):
        if t.get('annotation_required') and '@Test' not in text:
            errs.append('Missing @Test annotation')
        # method prefix
        prefix = t.get('test_methods_prefix','test')
        for m in re.finditer(
          r'^\s*public\s+void\s+(\w+)\s*\(', text, re.M):
            nm = m.group(1)
            ln_no = text[:m.start()].count('\n')+1
            if not nm.startswith(prefix):
                errs.append(f'Line {ln_no}: test "{nm}" must start "{prefix}"')
        # assertEquals delta
        for m in re.finditer(r'assertEquals\s*\(', text):
            start = m.end(); depth = 1; i = start; buf = ''
            while i<len(text) and depth>0:
                c = text[i]
                if c=='(': depth+=1
                elif c==')': depth-=1
                buf += c; i+=1
            args = split_args(buf[:-1])
            if (t.get('require_assert_equals_delta')
                and len(args)==2
                and (re.search(r'\d+\.\d+',args[0])
                     or re.search(r'\d+\.\d+',args[1]))):
                ln_no = text[:m.start()].count('\n')+1
                errs.append(
                  f'Line {ln_no}: assertEquals missing delta for double')

    # OVERRIDE enforcement (configurable)
    if s.get('require_override'):
        ext = re.search(r'public\s+class\s+\w+\s+extends\s+(\w+)', text)
        if ext:
            parent = ext.group(1)
            root = path.split(os.sep+'src'+os.sep)[0]
            sup = os.path.join(root, 'src', f'{parent}.java')
            if os.path.isfile(sup):
                sup_txt = open(sup, encoding='utf-8').read()
                sup_sigs = set(re.findall(
                    r'^\s*(?:public|protected)\s+\w[\w<>\[\]]*\s+(\w+\(.*?\))\s*\{',
                    sup_txt, re.M
                ))
                for m in re.finditer(
                    r'^\s*(public|protected)\s+\w[\w<>\[\]]*\s+(\w+\(.*?\))\s*\{',
                    text, re.M
                ):
                    sig = m.group(2)
                    ln_no = text[:m.start()].count('\n') + 1
                    if sig in sup_sigs:
                        idx = ln_no - 2
                        while idx >= 0 and lines[idx].strip() == '':
                            idx -= 1
                        if idx < 0 or lines[idx].strip() != '@Override':
                            errs.append(f'Line {ln_no}: missing @Override on {sig}')
    return errs

def parse_test_reports_tree(report_dir):
    results = {}
    if not os.path.isdir(report_dir):
        return results
    for fn in os.listdir(report_dir):
        if fn.startswith("TEST-") and fn.endswith(".xml"):
            full = os.path.join(report_dir, fn)
            tree = ET.parse(full)
            root = tree.getroot()
            suite = root.attrib.get('name', fn[5:-4])
            cases = []
            for tc in root.findall('testcase'):
                name = tc.attrib.get('name')
                if tc.find('failure') is not None:
                    status, msg = "FAIL", tc.find('failure').attrib.get('message','').strip()
                elif tc.find('error')   is not None:
                    status, msg = "ERROR", tc.find('error').attrib.get('message','').strip()
                elif tc.find('skipped') is not None:
                    status, msg = "SKIPPED", ""
                else:
                    status, msg = "PASS", ""
                cases.append((name, status, msg))
            results[suite] = cases
    return results

def main():
    p = argparse.ArgumentParser(description='WebCAT-style compliance & test runner')
    p.add_argument('path', nargs='?', help='project root (with src/) or stdin')
    p.add_argument('-p','--profile', default='CS2114', help='rules template')
    p.add_argument('--max-line-length', type=int, help='override max_line_length')
    p.add_argument('--no-javadoc', action='store_true', help='disable JavaDoc checks')
    p.add_argument('--no-author', action='store_true', help='disable @author check')
    p.add_argument('--no-version', action='store_true', help='disable @version check')
    p.add_argument('--allow-globals', action='store_true', help='allow global/static fields')
    p.add_argument('--allow-empty', action='store_true', help='allow empty methods')
    p.add_argument('--allow-unused', action='store_true', help='allow unused private methods')
    p.add_argument('--no-annotations', action='store_true', help='disable @Test checks')
    p.add_argument('--no-delta', action='store_true', help='disable assertEquals-delta checks')
    p.add_argument('--no-method-cov', action='store_true', help='disable 100% method coverage')
    p.add_argument('--no-branch-cov', action='store_true', help='disable 100% branch coverage')
    p.add_argument('--no-override', action='store_true', help='disable @Override enforcement')
    p.add_argument('--run-tests', action='store_true', help='compile & run tests via Maven')
    p.add_argument('--run-main', action='store_true', help='after tests, run any main()')
    p.add_argument('--external-jar', help='path to external student.jar for tests')
    p.add_argument('--debug', action='store_true', help='enable debug output')
    p.add_argument('--version', action='version', version=__version__,
                   help="show version and exit")
    args = p.parse_args()

    # Expand ~ and turn into absolute paths
    if args.path:
        args.path = os.path.abspath(os.path.expanduser(args.path))
    if args.external_jar:
        args.external_jar = os.path.abspath(os.path.expanduser(args.external_jar))

    global DEBUG
    DEBUG = args.debug
    if DEBUG:
        print("🔍 Debug:", args)

    rules = override_rules(load_rules(args.profile), args)

    # STYLE & TEST checks
    failed = False
    sources = collect_sources(args.path)
    if DEBUG:
        print("🔍 Debug: source files found:", sources)
    for src in sources:
        errs = check_file(src, rules)
        if errs:
            failed = True
            print(f'\n== {src} ==')
            for e in errs:
                print('  •', e)
    print('\n❌ Style/Test checks failed' if failed else '\n✅ Style/Test checks passed')

    # RUN TESTS & COVERAGE
    if args.run_tests:
        if not args.path:
            sys.exit('Error: --run-tests requires project root')

        ensure_pom(args.path, rules)

        mvn_cmd = ['mvn']
        if DEBUG:
            mvn_cmd.append('-X')
        mvn_cmd += ['-q','clean','verify']
        if DEBUG:
            print("🔍 Debug: running Maven:", ' '.join(mvn_cmd))
        subprocess.run(mvn_cmd, cwd=args.path, check=True)
        if DEBUG:
            print("🔍 Debug: Maven clean verify completed")

        # coverage
        rpt = os.path.join(args.path, 'target', 'site', 'jacoco', 'jacoco.xml')
        if not os.path.isfile(rpt):
            sys.exit(f'❌ Coverage report missing at {rpt}')
        miss_m, cov_m = parse_coverage(rpt)['METHOD']
        miss_b, cov_b = parse_coverage(rpt)['BRANCH']
        cov_rules = rules['testing']
        if cov_rules.get('require_full_method_coverage') and miss_m > 0:
            sys.exit(f'❌ Method coverage {(cov_m/(miss_m+cov_m))*100:.1f}% <100%')
        if cov_rules.get('require_full_branch_coverage') and miss_b > 0:
            sys.exit(f'❌ Branch coverage {(cov_b/(miss_b+cov_b))*100:.1f}% <100%')

        # pretty-print tree-style test results
        print("\n🧪 Test results:")
        tree = parse_test_reports_tree(os.path.join(args.path, 'target', 'surefire-reports'))
        suites = sorted(tree.items())
        for i, (suite, cases) in enumerate(suites):
            suite_marker = '└─' if i==len(suites)-1 else '├─'
            print(f"{suite_marker} {suite}")
            for j, (test, status, msg) in enumerate(cases):
                case_marker = '└─' if j==len(cases)-1 else '├─'
                symbol = {"PASS":"✅","FAIL":"❌","ERROR":"❌","SKIPPED":"⏭️"}[status]
                info = f": {msg}" if msg else ""
                print(f"    {case_marker} {test} {symbol}{info}")

        # coverage summary
        total_m = miss_m + cov_m
        total_b = miss_b + cov_b
        pct_m = (cov_m/total_m*100) if total_m>0 else 100
        pct_b = (cov_b/total_b*100) if total_b>0 else 100
        print("\n📊 Coverage summary:")
        print(f"  🧩 Method coverage: {pct_m:.1f}% ({cov_m}/{total_m})")
        print(f"  🍃 Branch coverage: {pct_b:.1f}% ({cov_b}/{total_b})")

        # optional main()
        if args.run_main:
            for src in sources:
                txt = open(src, encoding='utf-8').read()
                if 'public static void main' in txt:
                    cls = os.path.splitext(os.path.basename(src))[0]
                    print(f'▶️ Running main() in {cls}')
                    subprocess.run(
                      ['java','-cp', os.path.join(args.path,'target','classes'), cls],
                      check=False)
                    break

    sys.exit(1 if failed else 0)

if __name__ == '__main__':
    main()

