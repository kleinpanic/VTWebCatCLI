#!/usr/bin/env python3
"""
WebcatCLI.py

A self-contained WebCAT-style pre-submission checker:
  - Coding/Styling rules
  - Correctness/Testing rules
  - Auto-generates a minimal Maven pom.xml (with JUnit & JaCoCo)
  - Runs `mvn test` to compile, test, and produce coverage
  - Parses JaCoCo XML for 100% method & branch coverage
  - Enforces @Override on overridden methods (configurable)
  - Optional `--run-main` to invoke your main() after tests
"""

import argparse, json, os, re, subprocess, sys, tempfile, xml.etree.ElementTree as ET

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

def ensure_pom(root):
    pom = os.path.join(root, 'pom.xml')
    if os.path.exists(pom): return
    content = """<project xmlns="http://maven.apache.org/POM/4.0.0" ...> ... </project>"""
    with open(pom,'w',encoding='utf-8') as f:
        f.write(content)
    print(f'ℹ️ Generated minimal pom.xml in {root}')

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
            # skip constructor
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
        ext = re.search(
          r'public\s+class\s+\w+\s+extends\s+(\w+)', text)
        if ext:
            parent = ext.group(1)
            root = path.split(os.sep+'src'+os.sep)[0]
            sup = os.path.join(root,'src',f'{parent}.java')
            if os.path.isfile(sup):
                sup_txt = open(sup,encoding='utf-8').read()
                sup_methods = set(re.findall(
                  r'^\s*(?:public|protected)\s+\w[\w<>\[\]]*\s+(\w+)\(.*\)\s*\{',
                  sup_txt, re.M))
                for m in re.finditer(
                  r'^\s*(public|protected)\s+\w[\w<>\[\]]*\s+(\w+)\(.*\)\s*\{',
                  text, re.M):
                    nm = m.group(2)
                    ln_no = text[:m.start()].count('\n')+1
                    if nm in sup_methods:
                        idx = ln_no - 2
                        while idx>=0 and lines[idx].strip()=='':
                            idx -= 1
                        if idx<0 or lines[idx].strip()!='@Override':
                            errs.append(
                              f'Line {ln_no}: missing @Override on {nm}()')

    return errs

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
    args = p.parse_args()

    rules = override_rules(load_rules(args.profile), args)

    failed = False
    for src in collect_sources(args.path):
        errs = check_file(src, rules)
        if errs:
            failed = True
            print(f'\n== {src} ==')
            for e in errs:
                print('  •', e)
    print('\n❌ Style/Test checks failed' if failed else '\n✅ Style/Test checks passed')

    if args.run_tests:
        if not args.path:
            sys.exit('Error: --run-tests requires project root')
        ensure_pom(args.path)
        subprocess.run(['mvn','-q','clean','test'], cwd=args.path, check=True)
        rpt = os.path.join(args.path,'target','site','jacoco','jacoco.xml')
        if not os.path.isfile(rpt):
            sys.exit(f'❌ Coverage report missing at {rpt}')
        miss_m, cov_m = parse_coverage(rpt)['METHOD']
        miss_b, cov_b = parse_coverage(rpt)['BRANCH']
        cov = rules['testing']
        if cov.get('require_full_method_coverage') and miss_m>0:
            sys.exit(
              f'❌ Method coverage {(cov_m/(miss_m+cov_m))*100:.1f}% <100%')
        if cov.get('require_full_branch_coverage') and miss_b>0:
            sys.exit(
              f'❌ Branch coverage {(cov_b/(miss_b+cov_b))*100:.1f}% <100%')
        print('✅ Coverage checks passed')
        if args.run_main:
            for src in collect_sources(args.path):
                txt = open(src,encoding='utf-8').read()
                if 'public static void main' in txt:
                    cls = os.path.splitext(os.path.basename(src))[0]
                    print(f'▶️ Running main() in {cls}')
                    subprocess.run(
                      ['java','-cp',
                       os.path.join(args.path,'target','classes'),
                       cls], check=False)
                    break

    sys.exit(1 if failed else 0)

if __name__=='__main__':
    main()

