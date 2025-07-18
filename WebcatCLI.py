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
  - Optional `--no-cleanup` to preserve generated files
  - `--version` to show current CLI version
"""

import argparse
import atexit
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET

__version__ = "1.1.2"
DEBUG = False

# Track everything we create so we can delete it later:
CREATED = []
# Flip to True when we should skip cleanup (debug or --no-cleanup)
SKIP_CLEANUP = False

def cleanup():
    """Delete any files or directories we recorded in CREATED."""
    if SKIP_CLEANUP:
        return
    for path in reversed(CREATED):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path):
                os.remove(path)
        except Exception as e:
            if DEBUG:
                print(f"⚠️ Cleanup failed for {path}: {e}")
    CREATED.clear()

# Ensure cleanup() runs on every normal exit (and SystemExit)
atexit.register(cleanup)

# -------------------------------------------------------------------
# Auto-locate or download jacococli.jar
# -------------------------------------------------------------------
def locate_or_download_jacococli(project_root):
    script_dir = os.path.dirname(__file__)
    global_jar = os.path.join(script_dir, 'jacococli.jar')
    if os.path.isfile(global_jar):
        if DEBUG:
            print(f"🔍 Using global jacococli.jar at {global_jar}")
        return global_jar

    jar_dir = os.path.join(project_root, 'lib')
    os.makedirs(jar_dir, exist_ok=True)
    project_jar = os.path.join(jar_dir, 'jacococli.jar')
    if not os.path.isfile(project_jar):
        url = (
            "https://repo1.maven.org/maven2/"
            "org/jacoco/org.jacoco.cli/0.8.8/"
            "org.jacoco.cli-0.8.8-nodeps.jar"
        )
        print(f"⬇️  Downloading JaCoCo CLI to {project_jar}")
        urllib.request.urlretrieve(url, project_jar)
        CREATED.append(project_jar)
    return project_jar

# -------------------------------------------------------------------
# Helpers for @param / @return validation
# -------------------------------------------------------------------
def parse_methods_and_javadoc(lines):
    methods = []
    javadoc = []
    in_jdoc = False
    for idx, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped.startswith('/**'):
            in_jdoc = True
            javadoc = [ln]
            continue
        if in_jdoc:
            javadoc.append(ln)
            if stripped.endswith('*/'):
                in_jdoc = False
            continue
        m = re.match(r'^\s*(public|protected|private)\s+([\w<>\[\]]+)\s+(\w+)\s*\((.*?)\)', ln)
        if m:
            return_type = m.group(2)
            name = m.group(3)
            params_str = m.group(4)
            params = [p.strip().split()[-1] for p in params_str.split(',') if p.strip()]
            methods.append((idx + 1, name, params, return_type, javadoc.copy()))
            javadoc = []
    return methods

def check_javadoc_params_and_return(line_no, name, params, return_type, javadoc, errs):
    if not javadoc:
        return
    text = ''.join(javadoc)
    param_tags = re.findall(r'@param\s+(\w+)', text)
    has_return = '@return' in text

    for p in params:
        if p not in param_tags:
            errs.append(f'Line {line_no}: missing @param for "{p}" in method {name}()')
    for p in param_tags:
        if p not in params:
            errs.append(f'Line {line_no}: @param "{p}" does not match any parameter in {name}()')
    if return_type and return_type != 'void':
        if not has_return:
            errs.append(f'Line {line_no}: missing @return in Javadoc for method {name}()')
    else:
        if has_return:
            errs.append(f'Line {line_no}: unexpected @return in void method {name}()')

# -------------------------------------------------------------------
# Core functions
# -------------------------------------------------------------------
def load_rules(profile):
    path = os.path.join(os.path.dirname(__file__), 'templates', f'{profile}.rules.json')
    if not os.path.isfile(path):
        sys.exit(f'Error: profile "{profile}" not found')
    return json.load(open(path, encoding='utf-8'))

def override_rules(rules, args):
    s = rules['style']
    t = rules['testing']

    if args.max_line_length    is not None: s['max_line_length']         = args.max_line_length
    if args.no_javadoc:        s['javadoc_required']                   = False
    if args.no_author:         s['javadoc_require_author']             = False
    if args.no_version:        s['javadoc_require_version']            = False
    if args.allow_globals:     s['check_global_variable_usage']        = False
    if args.allow_empty:       s['no_empty_methods']                   = False
    if args.allow_unused:      s['no_unused_methods']                  = False
    if args.no_override:       s['require_override']                   = False
    if args.no_annotations:    t['annotation_required']                = False
    if args.no_delta:          t['require_assert_equals_delta']        = False
    if args.no_method_cov:     t['require_full_method_coverage']       = False
    if args.no_branch_cov:     t['require_full_branch_coverage']       = False
    if args.external_jar:      rules['external_jar']                   = args.external_jar

    if args.no_package_annotation: s['require_package_annotation'] = False
    if args.no_package_javadoc:    s['require_package_javadoc']    = False

    return rules

def collect_sources(path):
    if path is None:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.java',
                                          mode='w', encoding='utf-8')
        content = sys.stdin.read()
        tmp.write(content)
        tmp.close()
        CREATED.append(tmp.name)
        return [tmp.name]

    src = os.path.join(path, 'src')
    if not os.path.isdir(src):
        sys.exit(f'Error: expected directory "{src}"')
    out = []
    for root, _, files in os.walk(src):
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
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-surefire-plugin</artifactId>
        <version>2.22.2</version>
        <configuration><useModulePath>false</useModulePath></configuration>
      </plugin>
      <plugin>
        <groupId>org.jacoco</groupId>
        <artifactId>jacoco-maven-plugin</artifactId>
        <version>0.8.5</version>
        <executions>
          <execution><id>prepare-agent</id><goals><goal>prepare-agent</goal></goals></execution>
          <execution>
            <id>report</id><phase>verify</phase><goals><goal>report</goal></goals>
            <configuration><formats><format>XML</format><format>HTML</format></formats></configuration>
          </execution>
        </executions>
      </plugin>
      <plugin>
        <groupId>org.codehaus.mojo</groupId>
        <artifactId>build-helper-maven-plugin</artifactId>
        <version>3.2.0</version>
        <executions>
          <execution><id>add-flat-src</id><phase>generate-sources</phase><goals><goal>add-source</goal></goals>
            <configuration><sources><source>src</source></sources></configuration>
          </execution>
          <execution><id>add-flat-test</id><phase>generate-test-sources</phase><goals><goal>add-test-source</goal></goals>
            <configuration><sources><source>src</source></sources></configuration>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>
</project>'''
    with open(pom, 'w', encoding='utf-8') as f:
        f.write(content)
    CREATED.append(pom)
    print(f'ℹ️  Generated minimal pom.xml in {root}')
    if DEBUG:
        print("Debug: Generated pom.xml content:")
        print(content)

def parse_coverage(xmlpath):
    tree = ET.parse(xmlpath)
    tot  = {'METHOD': (0,0), 'BRANCH': (0,0)}
    for c in tree.findall('.//counter'):
        t = c.get('type')
        if t in tot:
            tot[t] = (int(c.get('missed')), int(c.get('covered')))
    return tot

# -------------------------------------------------------------------
# XML-parsing helpers for detailed tree
# -------------------------------------------------------------------
def parse_coverage_details(xmlpath):
    tree = ET.parse(xmlpath)
    root = tree.getroot()
    details = {}
    for pkg in root.findall('package'):
        pkg_name = pkg.get('name')
        details[pkg_name] = {}
        for cls in pkg.findall('class'):
            cls_name = cls.get('name').split('/')[-1]
            methods = []
            for m in cls.findall('method'):
                miss_i = miss_b = 0
                for cnt in m.findall('counter'):
                    if cnt.get('type') == 'METHOD':
                        miss_i = int(cnt.get('missed'))
                    if cnt.get('type') == 'BRANCH':
                        miss_b = int(cnt.get('missed'))
                if miss_i or miss_b:
                    methods.append((m.get('name'), miss_i, miss_b))
            if methods:
                details[pkg_name][cls_name] = methods
    return details

def print_coverage_tree(detailed):
    pkgs = list(detailed.items())
    for pi, (pkg, classes) in enumerate(pkgs):
        pkg_marker = '└─' if pi == len(pkgs)-1 else '├─'
        print(f"{pkg_marker} package {pkg}")
        cls_items = list(classes.items())
        for ci, (cls, methods) in enumerate(cls_items):
            cls_marker = '└─' if ci == len(cls_items)-1 else '├─'
            print(f"    {cls_marker} class {cls}")
            for mi, (mname, mm, mb) in enumerate(methods):
                m_marker = '└─' if mi == len(methods)-1 else '├─'
                print(f"        {m_marker} {mname}() — missed methods:{mm}, branches:{mb}")

def split_args(s):
    parts, cur, depth, in_str = [], '', 0, False
    qc = None
    for ch in s:
        if ch in "\"'":
            if not in_str:
                in_str, qc = True, ch
            elif qc == ch:
                in_str = False
            cur += ch
            continue
        if in_str:
            cur += ch
            continue
        if ch == '(':
            depth += 1; cur += ch; continue
        if ch == ')':
            depth -= 1; cur += ch; continue
        if ch == ',' and depth == 0:
            parts.append(cur.strip()); cur = ''; continue
        cur += ch
    if cur.strip(): parts.append(cur.strip())
    return parts

def check_file(path, rules):
    errs = []
    lines = open(path, encoding='utf-8').read().splitlines(keepends=True)
    text  = ''.join(lines)
    s, t = rules['style'], rules['testing']

    # PACKAGE-level checks…
    rel = os.path.relpath(path)
    parts = rel.split(os.sep)
    nested = 'src' in parts and len(parts) > parts.index('src') + 2
    if nested and s.get('require_package_annotation', True):
        pkg_match = re.search(r'^\s*package\s+[\w\.]+;', text, re.M)
        if not pkg_match:
            errs.append('Missing package declaration')
        elif s.get('require_package_javadoc', True):
            pkg_line = text[:pkg_match.start()].count('\n') + 1
            idx = pkg_line - 2
            while idx >= 0 and (lines[idx].strip() in ('',) or lines[idx].strip().startswith('@')):
                idx -= 1
            prev = lines[idx].strip() if idx >= 0 else ''
            if '@package' not in prev:
                errs.append(f'Line {pkg_line}: missing Javadoc @package tag before package statement')

    # STYLE checks…
    in_jdoc = False
    for i, ln in enumerate(lines, 1):
        stripped = ln.lstrip()
        if stripped.startswith('/**'): in_jdoc = True
        if in_jdoc:
            if '*/' in stripped: in_jdoc = False
            continue
        if stripped.startswith('*') or stripped.startswith('//'): continue
        if s.get('no_tabs') and '\t' in ln:
            errs.append(f'Line {i}: tab found (use spaces)')
        m = re.match(r'^( +)', ln)
        if m:
            spc = s['indentation']['spaces_per_indent']
            if len(m.group(1)) % spc != 0:
                errs.append(f'Line {i}: indent of {len(m.group(1))} spaces not multiple of {spc}')

    ml = s.get('max_line_length', -1)
    if ml > 0:
        for i, ln in enumerate(lines, 1):
            if len(ln.rstrip('\n')) > ml:
                errs.append(f'Line {i}: length {len(ln.rstrip())}>{ml}')

    if s.get('one_public_class_per_file'):
        pubs = re.findall(r'^\s*public\s+(?:class|interface)\s+\w+', text, re.M)
        if len(pubs) > 1:
            errs.append(f'{len(pubs)} public types in one file')

    # GLOBAL STATIC FIELDS — now usage-checked instead of flat-deny
    if s.get('check_global_variable_usage', False):
        for m in re.finditer(
                r'^\s*(?:public|protected|private)?\s+static\s+[\w<>\[\]]+\s+(\w+)\s*(?:=|;)',
                text, re.M):
            name = m.group(1)
            ln_no = text[:m.start()].count('\n') + 1
            usage = len(re.findall(r'\b' + re.escape(name) + r'\b', text)) - 1
            if usage <= 1:
                errs.append(
                    f'Line {ln_no}: static field "{name}" only used {usage+1} time(s); '
                    'declare a local or use it more than once'
                )

    # EMPTY METHODS
    if s.get('no_empty_methods'):
        for m in re.finditer(r'\)\s*\{\s*\}', text):
            ln_no = text[:m.start()].count('\n') + 1
            errs.append(f'Line {ln_no}: empty method body')

    # UNUSED PRIVATE METHODS
    if s.get('no_unused_methods'):
        for name in re.findall(r'private\s+\w+\s+(\w+)\(', text):
            rest = text[text.find(name):]
            if not re.search(r'\b' + name + r'\s*\(', rest[len(name):]):
                errs.append(f'unused private method "{name}"')

    # JAVADOC on classes & methods…
    if s.get('javadoc_required'):
        for m in re.finditer(r'^\s*public\s+class\s+(\w+)', text, re.M):
            cn = m.group(1); ln_no = text[:m.start()].count('\n') + 1
            idx = ln_no - 2
            while idx >= 0 and (lines[idx].strip() in ('',) or lines[idx].strip().startswith('@')):
                idx -= 1
            if idx < 0 or not lines[idx].strip().endswith('*/'):
                errs.append(f'Line {ln_no}: missing JavaDoc for class {cn}')
        for m in re.finditer(r'^\s*(public|protected)\s+\w[\w<>\[\]]*\s+(\w+)\(.*\)\s*\{', text, re.M):
            mn = m.group(2); ln_no = text[:m.start()].count('\n') + 1
            if re.search(rf'public\s+class\s+{mn}\b', text):
                continue
            idx = ln_no - 2
            while idx >= 0 and (lines[idx].strip() in ('',) or lines[idx].strip().startswith('@')):
                idx -= 1
            if idx < 0 or not lines[idx].strip().endswith('*/'):
                errs.append(f'Line {ln_no}: missing JavaDoc for method {mn}()')

    # JAVADOC author/version
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

    # PARAM/RETURN tags
    methods = parse_methods_and_javadoc(lines)
    for line_no, name, params, return_type, javadoc in methods:
        if javadoc:
            check_javadoc_params_and_return(line_no, name, params, return_type, javadoc, errs)

    return errs

def parse_test_reports_tree(report_dir):
    results = {}
    if not os.path.isdir(report_dir):
        return results
    for fn in os.listdir(report_dir):
        if fn.startswith("TEST-") and fn.endswith(".xml"):
            full = os.path.join(report_dir, fn)
            tree = ET.parse(full); root = tree.getroot()
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

def run_jacoco_cli_report(project_root, jar_path):
    """
    Run jacococli.jar to regenerate the XML report, then parse it.
    """
    exec_file  = os.path.join(project_root, 'target', 'jacoco.exec')
    class_dir  = os.path.join(project_root, 'target', 'classes')
    xml_report = os.path.join(project_root, 'target', 'site', 'jacoco', 'jacoco.xml')
    if not os.path.isfile(jar_path):
        print(f"⚠️  jacococli.jar not found at {jar_path}; cannot regenerate XML")
        return
    cmd = [
        'java', '-jar', jar_path,
        'report', exec_file,
        '--classfiles', class_dir,
        '--xml', xml_report
    ]
    try:
        subprocess.run(cmd, cwd=project_root, check=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("⚠️  Failed to run jacococli.jar report; falling back to existing XML")
    print("\n🔎 Coverage gaps (from regenerated XML):")
    detailed = parse_coverage_details(xml_report)
    print_coverage_tree(detailed)

def main():
    p = argparse.ArgumentParser(description='WebCAT-style compliance & test runner')
    # Argparse provides -h/--help. 
    p.add_argument('path', nargs='?', help='project root (with src/) or stdin')
    p.add_argument('-p','--profile', default='CS2114', help='rules template')
    p.add_argument('--max-line-length', type=int, help='override max_line_length')
    p.add_argument('--no-javadoc', action='store_true', help='disable JavaDoc checks')
    p.add_argument('--no-author', action='store_true', help='disable @author check')
    p.add_argument('--no-version', action='store_true', help='disable @version check')
    p.add_argument('--allow-globals', action='store_true',
                   help='skip usage-check on static fields')
    p.add_argument('--allow-empty', action='store_true', help='allow empty methods')
    p.add_argument('--allow-unused', action='store_true', help='allow unused private methods')
    p.add_argument('--no-annotations', action='store_true', help='disable @Test checks')
    p.add_argument('--no-delta', action='store_true', help='disable assertEquals-delta checks')
    p.add_argument('--no-method-cov', action='store_true', help='disable 100% method coverage')
    p.add_argument('--no-branch-cov', action='store_true', help='disable 100% branch coverage')
    p.add_argument('--enable-cli-report', action='store_true',
                   help='use jacococli.jar to regenerate the XML report before parsing')
    p.add_argument('--no-override', action='store_true', help='disable @Override enforcement')
    p.add_argument('--no-cleanup', action='store_true',
                   help='preserve generated files/directories after exit')
    p.add_argument('--cleanup', action='store_true',
                   help='force cleanup even in debug mode (overrides --no-cleanup)')
    p.add_argument('--run-tests', action='store_true', help='compile & run tests via Maven')
    p.add_argument('--run-main', action='store_true', help='after tests, run any main()')
    p.add_argument('--external-jar', help='path to external student.jar for tests')
    p.add_argument('--no-package-annotation', action='store_true',
                   help='skip scanning/enforcing any @package Javadoc tags')
    p.add_argument('--no-package-javadoc', action='store_true',
                   help='when scanning @package, do not require a preceding @package tag')
    p.add_argument('--debug', action='store_true', help='enable debug output')
    p.add_argument('--version', action='version', version=__version__, help="show version and exit")
    args = p.parse_args()

    if args.path:
        args.path = os.path.abspath(os.path.expanduser(args.path))
    if args.external_jar:
        args.external_jar = os.path.abspath(os.path.expanduser(args.external_jar))

    global DEBUG, SKIP_CLEANUP
    DEBUG = args.debug
    if DEBUG:
        # Debug Implies no-cleanup is true, unless explicitly indicated
        # otherwise with the use of --cleanup. 
        if not args.cleanup:
            args.no_cleanup = True
        print("🔍 Debug:", args)
    # if --cleanup is passed, always run cleanup; otherwise 
    # debug implies --no-cleanup, and --no-cleanup should be prioritized as a command. 
    # always honor --no-cleanup when passed.
    SKIP_CLEANUP = args.no_cleanup and not args.cleanup

    # Handle Ctrl-C / SIGTERM cleanly
    def _sig_handler(signum, frame):
        print("\n🔨 Interrupted; cleaning up...")
        sys.exit(1)
    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    failed = False
    sources = collect_sources(args.path)
    if DEBUG:
        print("🔍 Debug: source files found:", sources)
    for src in sources:
        errs = check_file(src, override_rules(load_rules(args.profile), args))
        if errs:
            failed = True
            print(f'\n== {src} ==')
            for e in errs:
                print('  •', e)

    print('\n❌ Style/Test checks failed' if failed else '\n✅ Style/Test checks passed')

    if args.run_tests:
        if not args.path:
            sys.exit('Error: --run-tests requires project root')

        rules = override_rules(load_rules(args.profile), args)
        ensure_pom(args.path, rules)

        mvn_cmd = ['mvn']
        if DEBUG:
            mvn_cmd.append('-X')
        mvn_cmd += ['-q', 'clean', 'verify']
        if DEBUG:
            print("🔍 Debug: running Maven:", ' '.join(mvn_cmd))
        subprocess.run(mvn_cmd, cwd=args.path, check=True)

        # Record the Maven-generated 'target' directory for cleanup
        target_dir = os.path.join(args.path, 'target')
        if os.path.isdir(target_dir):
            CREATED.append(target_dir)

        if DEBUG:
            print("🔍 Debug: Maven clean verify completed")

        rpt = os.path.join(args.path, 'target', 'site', 'jacoco', 'jacoco.xml')
        if not os.path.isfile(rpt):
            sys.exit(f'❌ Coverage report missing at {rpt}')

        miss_m, cov_m = parse_coverage(rpt)['METHOD']
        miss_b, cov_b = parse_coverage(rpt)['BRANCH']
        total_m = miss_m + cov_m
        total_b = miss_b + cov_b
        pct_m = (cov_m / total_m * 100) if total_m > 0 else 100.0
        pct_b = (cov_b / total_b * 100) if total_b > 0 else 100.0

        print("\n🧪 Test results:")
        tree = parse_test_reports_tree(os.path.join(args.path, 'target', 'surefire-reports'))
        suites = sorted(tree.items())
        for i, (suite, cases) in enumerate(suites):
            suite_marker = '└─' if i == len(suites)-1 else '├─'
            print(f"{suite_marker} {suite}")
            for j, (test, status, msg) in enumerate(cases):
                case_marker = '└─' if j == len(cases)-1 else '├─'
                symbol = {"PASS":"✅","FAIL":"❌","ERROR":"❌","SKIPPED":"⏭️"}[status]
                info = f": {msg}" if msg else ""
                print(f"    {case_marker} {test} {symbol}{info}")

        print("\n📊 Coverage summary:")
        print(f"  🧩 Method coverage: {pct_m:.1f}% ({cov_m}/{total_m})")
        print(f"  🍃 Branch coverage: {pct_b:.1f}% ({cov_b}/{total_b})")

        cov_rules = rules['testing']
        need_report = (
            cov_rules.get('require_full_method_coverage') and pct_m < 100
        ) or (
            cov_rules.get('require_full_branch_coverage') and pct_b < 100
        )

        if need_report:
            if args.enable_cli_report:
                # download the CLI jar and schedule its entire lib/ dir for cleanup
                jar_path = locate_or_download_jacococli(args.path)
                lib_dir = os.path.join(args.path, 'lib')
                if os.path.isdir(lib_dir) and not SKIP_CLEANUP:
                    CREATED.append(lib_dir)
                run_jacoco_cli_report(args.path, jar_path)
            else:
                print("\n🔎 Coverage gaps (from XML):")
                detailed = parse_coverage_details(rpt)
                print_coverage_tree(detailed)
            sys.exit(1)

        if args.run_main:
            for src in sources:
                txt = open(src, encoding='utf-8').read()
                if 'public static void main' in txt:
                    cls = os.path.splitext(os.path.basename(src))[0]
                    print(f'▶️ Running main() in {cls}')
                    subprocess.run(
                        ['java', '-cp', os.path.join(args.path, 'target', 'classes'), cls],
                        cwd=args.path, check=False
                    )
                    break

    sys.exit(1 if failed else 0)

if __name__ == '__main__':
    main()

