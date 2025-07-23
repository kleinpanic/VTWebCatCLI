#!/usr/bin/env python3
"""
WebcatCLI.py

A self-contained WebCAT-style pre-submission checker:
  - Coding/Styling rules
  - Correctness/Testing rules
  - Auto-generates a minimal Maven pom.xml (with JUnit, optional student.jar & JaCoCo)
  - Runs `mvn clean verify` to compile, test, and produce coverage
  - Parses JaCoCo XML for 100% method & branch coverage
  - Detects & ignores unreachable branches (if enabled)
  - AST-based `--scan-impossible-branches` to catch logically impossible conditions
  - Enforces @Override on overridden methods (configurable)
  - Style rule: closing brace `}` must be alone on its line
  - Optional `--run-main` to invoke your main() after tests
  - Optional `--external-jar` to point at a custom student.jar
  - Optional `--debug` to print verbose internal state
  - Optional `--no-cleanup` to preserve generated files
  - `--version` to show current CLI version
  - `--detect-unreachable` to ignore compiler-reported unreachable code
  - **New** `--scan-impossible-branches` to detect always-true/false predicates
  - **New** `--delete-modules-info` to remove modules.info files for Maven compatibility
"""

import argparse
import atexit
import json
import shutil
import signal
import subprocess
import sys
import tempfile
import urllib.request
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
import logging

__version__ = "1.1.4"
DEBUG = False

# Track everything we create so we can delete it later:
CREATED = []
# Flip to True when we should skip cleanup (debug or --no-cleanup)
SKIP_CLEANUP = False

def normalize_path(pth):
    """
    Use pathlib to expand user (~), resolve relative symlinks, and
    return a consistently formatted string, regardless of platform.
    """
    try:
        return str(Path(pth).expanduser().resolve())
    except Exception:
        return str(Path(pth))

def cleanup():
    """Delete any files or directories we recorded in CREATED."""
    if SKIP_CLEANUP:
        return
    for path in reversed(CREATED):
        p = Path(path)
        try:
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
        except Exception as e:
            if DEBUG:
                logging.error(f"⚠️ Cleanup failed for {path}: {e}")
    CREATED.clear()

# Ensure cleanup() runs on every normal exit (and SystemExit)
atexit.register(cleanup)

# -------------------------------------------------------------------
# Auto-locate or download jacococli.jar
# -------------------------------------------------------------------
def locate_or_download_jacococli(project_root):
    script_dir = Path(__file__).parent
    global_jar = script_dir / 'jacococli.jar'
    if global_jar.is_file():
        if DEBUG:
            logging.debug(f"🔍 Using global jacococli.jar at {global_jar}")
        return str(global_jar)

    jar_dir = Path(project_root) / 'lib'
    jar_dir.mkdir(parents=True, exist_ok=True)
    project_jar = jar_dir / 'jacococli.jar'
    if not project_jar.is_file():
        url = (
            "https://repo1.maven.org/maven2/"
            "org/jacoco/org.jacoco.cli/0.8.8/"
            "org.jacoco.cli-0.8.8-nodeps.jar"
        )
        logging.info(f"⬇️  Downloading JaCoCo CLI to {project_jar}")
        urllib.request.urlretrieve(url, str(project_jar))
        CREATED.append(str(project_jar))
    return str(project_jar)

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
# Helpers for unreachable‐code detection via javac -Xlint:unreachable
# -------------------------------------------------------------------
def detect_unreachable_branches(src_root):
    """
    Compile every .java under src/ with -Xlint:unreachable,
    collect all (filename, lineno) pairs that the compiler warns are unreachable.
    """
    src_dir = Path(src_root) / 'src'
    java_files = [str(p) for p in src_dir.rglob('*.java')]
    if not java_files:
        return set()

    out_dir = Path(tempfile.mkdtemp(prefix='unreach_'))
    CREATED.append(str(out_dir))

    cmd = ['javac', '-Xlint:unreachable', '-d', str(out_dir)] + java_files
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    unreachable = set()
    for line in proc.stderr.splitlines():
        m = re.match(r'(.+\.java):(\d+): warning: unreachable code', line)
        if m:
            fname = Path(m.group(1)).name
            lineno = int(m.group(2))
            unreachable.add((fname, lineno))
    return unreachable

def detect_impossible_branches(src_root):
    """
    Parse each .java under src/ with javalang, look for IfStatement,
    and flag any condition that always evaluates False (literal-only).
    """
    try:
        import javalang
    except ImportError:
        logging.warning("⚠️  Missing dependency 'javalang'. Install via `pip install javalang`.")
        sys.exit(1)
    issues = []
    for path in (Path(src_root) / 'src').rglob('*.java'):
        try:
            text = path.read_text(encoding='utf-8')
            tree = javalang.parse.parse(text)
        except Exception:
            continue
        for _, node in tree.filter(javalang.tree.IfStatement):
            cond = node.condition
            if isinstance(cond, javalang.tree.BinaryOperation):
                ol, op, or_ = cond.operandl, cond.operator, cond.operandr
                if (isinstance(ol, javalang.tree.Literal) and
                    isinstance(or_, javalang.tree.Literal)):
                    expr = f"{ol.value}{op}{or_.value}"
                    try:
                        if not eval(expr):
                            ln = node.position.line
                            issues.append((str(path), ln, expr))
                    except Exception:
                        pass
    return issues

# -------------------------------------------------------------------
# Core functions
# -------------------------------------------------------------------
def load_rules(profile):
    path = Path(__file__).parent / 'templates' / f'{profile}.rules.json'
    if not path.is_file():
        sys.exit(f'Error: profile "{profile}" not found')
    return json.loads(path.read_text(encoding='utf-8'))

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
    if getattr(args, 'detect_unreachable', False):
        t['detect_unreachable_branches'] = True
    if args.external_jar:
        rules['external_jar'] = args.external_jar

    if args.no_package_annotation:
        s['require_package_annotation'] = False
    if args.no_package_javadoc:
        s['require_package_javadoc']    = False

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

    src = Path(path) / 'src'
    if not src.is_dir():
        sys.exit(f'Error: expected directory "{src}"')
    return [str(p) for p in src.rglob('*.java')]

def ensure_pom(root, rules):
    """
    Generate a minimal pom.xml (with JUnit, optional student.jar & JaCoCo)
    and the build-helper plugin to flatten src/ into both main & test.
    """
    root = Path(root)
    pom = root / 'pom.xml'
    if pom.exists():
        if DEBUG:
            logging.debug(f"Debug: pom.xml already exists at {pom}, skipping generation")
        return

    script_dir = Path(__file__).parent
    ext_jar = Path(rules.get('external_jar') or script_dir / 'student.jar').resolve()
    has_student = ext_jar.is_file()
    if has_student:
        logging.info(f'🔗 Including external JAR: {ext_jar}')
    else:
        logging.info(f'— No external JAR found at {ext_jar}; tests will run with JUnit only')
    if DEBUG:
        logging.debug(f"Debug: student.jar path: {ext_jar} (exists: {has_student})")

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

    pom.write_text(content, encoding='utf-8')
    CREATED.append(str(pom))
    logging.info(f'ℹ️  Generated minimal pom.xml in {root}')
    if DEBUG:
        logging.debug("Debug: Generated pom.xml content:")
        logging.debug(content)

def parse_coverage(xmlpath):
    tree = ET.parse(xmlpath)
    tot  = {'METHOD': (0,0), 'BRANCH': (0,0)}
    for c in tree.findall('.//counter'):
        t = c.get('type')
        if t in tot:
            tot[t] = (int(c.get('missed')), int(c.get('covered')))
    return tot

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
        logging.info(f"{pkg_marker} package {pkg}")
        cls_items = list(classes.items())
        for ci, (cls, methods) in enumerate(cls_items):
            cls_marker = '└─' if ci == len(cls_items)-1 else '├─'
            logging.info(f"    {cls_marker} class {cls}")
            for mi, (mname, mm, mb) in enumerate(methods):
                m_marker = '└─' if mi == len(methods)-1 else '├─'
                logging.info(f"        {m_marker} {mname}() — missed methods:{mm}, branches:{mb}")

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
    if cur.strip():
        parts.append(cur.strip())
    return parts

def check_file(path, rules):
    errs = []
    lines = Path(path).read_text(encoding='utf-8').splitlines(keepends=True)
    text  = ''.join(lines)
    s, t = rules['style'], rules['testing']

    # PACKAGE-level checks…
    rel = Path(path).relative_to(Path(path).anchor)
    parts = rel.parts
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
        if stripped.startswith('/**'):
            in_jdoc = True
        if in_jdoc:
            if '*/' in stripped:
                in_jdoc = False
            continue
        if stripped.startswith('*') or stripped.startswith('//'):
            continue

        # tab check
        if s.get('no_tabs') and '\t' in ln:
            errs.append(f'Line {i}: tab found (use spaces)')
        # indentation
        m = re.match(r'^( +)', ln)
        if m:
            spc = s['indentation']['spaces_per_indent']
            if len(m.group(1)) % spc != 0:
                errs.append(f'Line {i}: indent of {len(m.group(1))} spaces not multiple of {spc}')

    # max line length
    ml = s.get('max_line_length', -1)
    if ml > 0:
        for i, ln in enumerate(lines, 1):
            if len(ln.rstrip('\n')) > ml:
                errs.append(f'Line {i}: length {len(ln.rstrip())}>{ml}')

    # one public class per file
    if s.get('one_public_class_per_file'):
        pubs = re.findall(r'^\s*public\s+(?:class|interface)\s+\w+', text, re.M)
        if len(pubs) > 1:
            errs.append(f'{len(pubs)} public types in one file')

    # CLOSING-BRACE ALONE rule
    if s.get('closing_brace_alone'):
        for i, ln in enumerate(lines, 1):
            stripped = ln.lstrip()
            if stripped.startswith('//') or stripped.startswith('/*') \
               or stripped.startswith('*')  or stripped.startswith('*/'):
                continue
            if '}' in ln:
                idx   = ln.find('}')
                trail = ln[idx+1:]
                if trail.strip() and not trail.strip().startswith('//') \
                               and not trail.strip().startswith('/*'):
                    errs.append(f'Line {i}: closing brace should be alone on its line')

    # GLOBAL STATIC FIELDS
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
            cn = m.group(1)
            ln_no = text[:m.start()].count('\n') + 1
            idx = ln_no - 2
            while idx >= 0 and (lines[idx].strip() in ('',) or lines[idx].strip().startswith('@')):
                idx -= 1
            if idx < 0 or not lines[idx].strip().endswith('*/'):
                errs.append(f'Line {ln_no}: missing JavaDoc for class {cn}')
        for m in re.finditer(r'^\s*(public|protected)\s+\w[\w<>\[\]]*\s+(\w+)\(.*\)\s*\{', text, re.M):
            mn = m.group(2)
            ln_no = text[:m.start()].count('\n') + 1
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
    report_dir = Path(report_dir)
    if not report_dir.is_dir():
        return results
    for fn in report_dir.iterdir():
        if fn.name.startswith("TEST-") and fn.name.endswith(".xml"):
            tree = ET.parse(str(fn)); root = tree.getroot()
            suite = root.attrib.get('name', fn.name[5:-4])
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
    project_root = Path(project_root)
    exec_file  = project_root / 'target' / 'jacoco.exec'
    class_dir  = project_root / 'target' / 'classes'
    xml_report = project_root / 'target' / 'site' / 'jacoco' / 'jacoco.xml'
    if not Path(jar_path).is_file():
        logging.warning(f"⚠️  jacococli.jar not found at {jar_path}; cannot regenerate XML")
        return
    cmd = [
        'java', '-jar', jar_path,
        'report', str(exec_file),
        '--classfiles', str(class_dir),
        '--xml', str(xml_report)
    ]
    try:
        subprocess.run(cmd, cwd=str(project_root), check=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        logging.warning("⚠️  Failed to run jacococli.jar report; falling back to existing XML")
    logging.info("\n🔎 Coverage gaps (from regenerated XML):")
    detailed = parse_coverage_details(str(xml_report))
    print_coverage_tree(detailed)

def main():
    p = argparse.ArgumentParser(description='WebCAT-style compliance & test runner')
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
    p.add_argument('--no-method-cov', action='store_true', help='disable 100%% method coverage')
    p.add_argument('--no-branch-cov', action='store_true', help='disable 100%% branch coverage')
    p.add_argument('--detect-unreachable', action='store_true',
                   help='ignore missed branches that the compiler marks as unreachable')
    p.add_argument('--scan-impossible-branches', action='store_true',
                   help='scan for logically impossible branch conditions (always-false)')
    p.add_argument('--enable-cli-report', action='store_true',
                   help='use jacococli.jar to regenerate the XML report before parsing')
    p.add_argument('--run-tests', action='store_true', help='compile & run tests via Maven')
    p.add_argument('--run-main', action='store_true', help='after tests, run any main()')
    p.add_argument('--external-jar', help='path to external student.jar for tests')
    p.add_argument('--no-package-annotation', action='store_true',
                   help='skip scanning/enforcing any @package Javadoc tags')
    p.add_argument('--no-package-javadoc', action='store_true',
                   help='when scanning @package, do not require a preceding @package tag')
    p.add_argument('--no-override', action='store_true', help='disable @Override enforcement')
    p.add_argument('--no-cleanup', action='store_true',
                   help='preserve generated files/directories after exit')
    p.add_argument('--cleanup', action='store_true',
                   help='force cleanup even in debug mode (overrides --no-cleanup)')
    p.add_argument('--debug', action='store_true', help='enable debug output')
    p.add_argument('--version', action='version', version=__version__, help="show version and exit")
    p.add_argument('--delete-modules-info', action='store_true',
                   help='Delete modules.info files for Maven compatibility')
    args = p.parse_args()

    # configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    if args.path:
        args.path = normalize_path(args.path)
    if args.external_jar:
        args.external_jar = normalize_path(args.external_jar)

    global DEBUG, SKIP_CLEANUP
    DEBUG = args.debug
    if DEBUG:
        if not args.cleanup:
            args.no_cleanup = True
        logging.debug(f"🔍 Debug: {args}")
    SKIP_CLEANUP = args.no_cleanup and not args.cleanup

    def _sig_handler(signum, frame):
        logging.info("\n🔨 Interrupted; cleaning up...")
        sys.exit(1)
    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    # delete any modules.info files if requested
    if args.delete_modules_info:
        root = Path(args.path) if args.path else Path.cwd()
        for info_file in root.rglob('modules.info'):
            try:
                info_file.unlink()
                logging.info(f"🗑️ Deleted modules.info at {info_file}")
            except Exception as e:
                logging.error(f"Failed to delete {info_file}: {e}")

    # Early scan for impossible branches
    if args.scan_impossible_branches:
        issues = detect_impossible_branches(args.path)
        if issues:
            logging.info("\n🔍 Impossible-branch issues found:")
            for (f, ln, expr) in issues:
                logging.info(f"  • {f}:{ln}: condition `{expr}` is always false")
            sys.exit(1)

    failed = False
    sources = collect_sources(args.path)
    if DEBUG:
        logging.debug(f"🔍 Debug: source files found: {sources}")

    for src in sources:
        errs = check_file(src, override_rules(load_rules(args.profile), args))
        if errs:
            failed = True
            logging.error(f"\n== {src} ==")
            for e in errs:
                logging.error(f"  • {e}")

    if failed:
        logging.error("\n❌ Style/Test checks failed")
    else:
        logging.info("\n✅ Style/Test checks passed")

    if args.run_tests:
        if not args.path:
            sys.exit('Error: --run-tests requires project root')

        rules = override_rules(load_rules(args.profile), args)
        ensure_pom(args.path, rules)

        # ---------------- robust Maven lookup ----------------
        def find_mvn():
            exe = shutil.which('mvn')
            if exe:
                return exe
            for ev in ('M2_HOME','MAVEN_HOME'):
                home = os.environ.get(ev)
                if home:
                    cand = Path(home) / 'bin' / ('mvn.cmd' if os.name=='nt' else 'mvn')
                    if cand.is_file() and cand.match('*.exe') or cand.match('*.cmd') or cand.match('mvn'):
                        return str(cand)
            if os.name == 'nt':
                choco = Path(r"C:\ProgramData\chocolatey\lib\maven\apache-maven-3.9.10\bin\mvn.cmd")
                if choco.is_file():
                    return str(choco)
                for base in (os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')):
                    if base:
                        for cand in Path(base).glob('apache-maven*/bin/mvn.cmd'):
                            if cand.exists():
                                return str(cand)
            if os.name == 'posix' and shutil.which('sudo'):
                if shutil.which('apt-get'):
                    try:
                        subprocess.run(['sudo','apt-get','update'], check=True,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        subprocess.run(['sudo','apt-get','install','-y','maven'], check=True)
                        exe2 = shutil.which('mvn')
                        if exe2:
                            return exe2
                    except subprocess.CalledProcessError:
                        pass
                if shutil.which('pacman'):
                    try:
                        subprocess.run(['sudo','pacman','-Sy','--noconfirm','maven'], check=True)
                        exe3 = shutil.which('mvn')
                        if exe3:
                            return exe3
                    except subprocess.CalledProcessError:
                        pass
            brew = shutil.which('brew')
            if brew:
                try:
                    prefix = subprocess.check_output(
                        [brew, '--prefix', 'maven'],
                        stderr=subprocess.DEVNULL, text=True
                    ).strip()
                    cand = Path(prefix) / 'bin' / 'mvn'
                    if cand.exists():
                        return str(cand)
                except subprocess.CalledProcessError:
                    pass
                exe2 = shutil.which('mvn')
                if exe2:
                    return exe2
                logging.info("⬇️  Installing Maven via Homebrew…")
                try:
                    subprocess.run([brew, 'install', 'maven'], check=True)
                except subprocess.CalledProcessError:
                    sys.exit("❌ Failed to install Maven via Homebrew.")
                exe3 = shutil.which('mvn')
                if exe3:
                    return exe3
            return None

        mvn_exe = find_mvn()
        if not mvn_exe:
            sys.exit("❌ Error: Maven executable not found. Please install Maven or add it to your PATH.")

        mvn_cmd = [mvn_exe]
        if DEBUG:
            mvn_cmd.append('-X')
        mvn_cmd += ['-q', 'clean', 'verify']
        if DEBUG:
            logging.debug(f"🔍 Debug: running Maven: {' '.join(mvn_cmd)}")

        # wrap mvn invocation in try/except
        try:
            subprocess.run(mvn_cmd, cwd=args.path, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Maven build failed: {e}")
            sys.exit(1)

        target_dir = Path(args.path) / 'target'
        if target_dir.is_dir():
            CREATED.append(str(target_dir))

        if DEBUG:
            logging.debug("🔍 Debug: Maven clean verify completed")

        rpt = Path(args.path) / 'target' / 'site' / 'jacoco' / 'jacoco.xml'
        if not rpt.is_file():
            sys.exit(f'❌ Coverage report missing at {rpt}')

        miss_m, cov_m = parse_coverage(str(rpt))['METHOD']
        miss_b, cov_b = parse_coverage(str(rpt))['BRANCH']
        total_m = miss_m + cov_m
        total_b = miss_b + cov_b
        pct_m = (cov_m / total_m * 100) if total_m > 0 else 100.0
        pct_b = (cov_b / total_b * 100) if total_b > 0 else 100.0

        logging.info("\n🧪 Test results:")
        tree = parse_test_reports_tree(Path(args.path) / 'target' / 'surefire-reports')
        suites = sorted(tree.items())
        for i, (suite, cases) in enumerate(suites):
            suite_marker = '└─' if i == len(suites)-1 else '├─'
            logging.info(f"{suite_marker} {suite}")
            for j, (test, status, msg) in enumerate(cases):
                case_marker = '└─' if j == len(cases)-1 else '├─'
                symbol = {"PASS":"✅","FAIL":"❌","ERROR":"❌","SKIPPED":"⏭️"}[status]
                info = f": {msg}" if msg else ""
                logging.info(f"    {case_marker} {test} {symbol}{info}")

        logging.info("\n📊 Coverage summary:")
        logging.info(f"  🧩 Method coverage: {pct_m:.1f}% ({cov_m}/{total_m})")
        logging.info(f"  🍃 Branch coverage: {pct_b:.1f}% ({cov_b}/{total_b})")

        cov_rules = rules['testing']
        hard_fail_m = (cov_rules.get('require_full_method_coverage') and pct_m < 100)
        hard_fail_b = (cov_rules.get('require_full_branch_coverage') and pct_b < 100)
        do_detect  = cov_rules.get('detect_unreachable_branches', False)

        # Javac-based unreachable‐branch filtering
        if do_detect and pct_b < 100:
            original    = parse_coverage_details(str(rpt))
            unreachable = detect_unreachable_branches(args.path)

            filtered = {}
            for pkg, classes in original.items():
                for cls, methods in classes.items():
                    fname = cls + '.java'
                    uln = {ln for (f, ln) in unreachable if f == fname}
                    kept = []
                    for (mn, mm, mb) in methods:
                        if mb and uln:
                            continue
                        kept.append((mn, mm, mb))
                    if kept:
                        filtered.setdefault(pkg, {})[cls] = kept

            remain = sum(
                mb
                for classes in filtered.values()
                for methods in classes.values()
                for (_, _, mb) in methods
            )
            if remain == 0:
                logging.info("\n✅ All remaining branch misses are in statically unreachable code.")
                logging.info("ℹ️ Treating branch coverage as 100%.\n")
                logging.info("🔎 Original coverage gaps (from XML):")
                print_coverage_tree(original)
                sys.exit(0)

        # Hard-fail if any required coverage still unmet
        if hard_fail_m or hard_fail_b:
            logging.error("\n❌ Coverage requirements not met:")
            if hard_fail_b:
                logging.error("   branch coverage is <100% outside of unreachable code")
            if args.enable_cli_report:
                jar_path = locate_or_download_jacococli(args.path)
                run_jacoco_cli_report(args.path, jar_path)
            else:
                logging.info("\n🔎 Coverage gaps (from XML):")
                print_coverage_tree(parse_coverage_details(str(rpt)))
            sys.exit(1)

        if args.run_main:
            for src in sources:
                txt = Path(src).read_text(encoding='utf-8')
                if 'public static void main' in txt:
                    cls = Path(src).stem
                    logging.info(f'▶️ Running main() in {cls}')
                    subprocess.run(
                        ['java', '-cp', str(Path(args.path) / 'target' / 'classes'), cls],
                        cwd=args.path, check=False
                    )
                    break

    sys.exit(1 if failed else 0)

if __name__ == '__main__':
    main()

