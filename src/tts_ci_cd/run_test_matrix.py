import base64, os, docker, datetime, argparse, sys, re, tarfile, io, shutil, requests, json, fnmatch
from collections import defaultdict
from jinja2 import Template
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from pathlib import Path

# --- Configuration Defaults ---
DEFAULT_PYTHON_VERSIONS = ["3.6.8", "3.7", "3.8", "3.9", "3.10", "3.11", "3.12", "3.13"]
BUILD_DEPS = ['toml', 'setuptools', 'setuptools_scm', 'pytest-cov', 'pip-audit', 'bandit']

# --- Audit Configuration ---
AUDIT_IGNORE_VULNS = []

# --- Highlighting Config ---
HIGHLIGHTED_LIBRARIES = [
    "tts_utilities", 
    "tts_html_utils", 
    "tts_papertrail", 
    "tts_data_utils",
    "tts_dexter",
    "tts_fresh",
    "tts_dtat",
    "tts_plan",
    "tts_spice",
    "tts_seq",
    "tts_dictionary_interface",
    "tts_tower",
    "tts_dante",
    "demosat_dictionary_interface",
    "demosat_data_utils",
    "demosat_dict",
    "demosat_seq",
    "demosat_fresh",
    "demosat_dante",
    "demosat_dexter",
    "demosat_plan",
    "demosat_tower",
]

# 1. All available internal Git URLs
INTERNAL_REPO_URLS = {
    "tts_starter_template":         "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/tts_starter_template.git",
    "tts_spice":                    "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/tts-spice.git",
    "tts_plan":                     "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/tts_plan.git",
    "tts_dtat":                     "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/dtat-library.git",
    "tts_utilities":                "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/tts_utilities.git",
    "tts_html_utils":               "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/html_utils.git",
    "tts_papertrail":               "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/papertrail.git",
    "tts_data_utils":               "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/data_utils.git",
    "tts_dexter":                   "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/dexter.git",
    "tts_dante":                    "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/dante.git",
    "tts_tower":                    "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/tower.git",
    "tts_seq":                      "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/tts_seq.git",
    "tts_fresh":                    "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/tts-fresh.git",
    "tts_dictionary_interface":     "git+ssh://git@github.com:NASA-JPL-Teamtools-Studio/tts_dictionary_interface.git",
    "jpl-time":                     "git+ssh://git@github.com:nasa-jpl/jpl_time.git",
    "demosat_dante":                "git+ssh://git@git@github.com:NASA-JPL-TTS-Demosat/demosat_dante.git",
    "demosat_dexter":               "git+ssh://git@git@github.com:NASA-JPL-TTS-Demosat/demosat_dexter.git",
    "demosat_plan":                 "git+ssh://git@git@github.com:NASA-JPL-TTS-Demosat/demosat_plan.git",
    "demosat_tower":                "git+ssh://git@git@github.com:NASA-JPL-TTS-Demosat/demosat_tower.git",
    "demosat_data_utils":           "git+ssh://git@git@github.com:NASA-JPL-TTS-Demosat/demosat_data_utils.git",
    "demosat_dict":                 "git+ssh://git@git@github.com:NASA-JPL-TTS-Demosat/demosat_dict.git",
    "demosat_dictionary_interface": "git+ssh://git@git@github.com:NASA-JPL-TTS-Demosat/demosat_dictionary_interface.git",
    "demosat_seq":                  "git+ssh://git@git@github.com:NASA-JPL-TTS-Demosat/demosat_seq.git",
    "demosat_fresh":                "git+ssh://git@git@github.com:NASA-JPL-TTS-Demosat/demosat-fresh.git",
}

# 2. Define the Tree
FULL_DEP_GRAPH = {
    "tts_dante":                    ["tts_utilities", "tts_html_utils", "tts_papertrail", "tts_data_utils"],
    "tts_data_utils":               ["tts_utilities", "tts_html_utils", "tts_papertrail"],
    "tts_dexter":                   ["tts_utilities", "tts_html_utils", "tts_papertrail", "tts_data_utils", 'jpl-time'],
    "tts_dictionary_interface":     ["tts_utilities"],
    "tts_dtat":                     ["tts_utilities"],
    "tts_html_utils":               ["tts_utilities"],
    "tts_fresh":                    ["tts_utilities", "tts_seq"],
    "tts_papertrail":               ["tts_utilities", "tts_html_utils", "tts_data_utils"],
    "tts_plan":                     ["tts_utilities", "tts_html_utils", "tts_papertrail", "tts_data_utils"],
    "tts_seq":                      ["tts_utilities", "tts_html_utils", "tts_papertrail", "tts_data_utils", "tts_dtat"],
    "tts_spice":                    ["tts_utilities"],
    "tts_starter_template":         ["tts_utilities"],
    "tts_tower":                    ["tts_utilities", "tts_html_utils", "tts_papertrail", "tts_data_utils", "jpl-time"],
    "tts_utilities":                [],
    "demosat_dante":                ["tts_utilities", "tts_html_utils", "tts_papertrail", "tts_data_utils", "tts_dante"],
    "demosat_data_utils":           ["tts_utilities", "tts_html_utils", "tts_papertrail", "tts_data_utils", "tts_spice"],
    "demosat_dexter":               ["tts_utilities", "tts_html_utils", "tts_papertrail", "tts_data_utils", "jpl-time", "tts_dexter"],
    "demosat_dictionary_interface": ["tts_utilities", "tts_dictionary_interface", "demosat_dict"],
    "demosat_fresh":                ["tts_utilities",  "tts_seq", "tts_fresh"],
    "demosat_plan":                 ["tts_utilities", "tts_html_utils", "tts_papertrail", "tts_data_utils", "tts_spice", "tts_plan"],
    "demosat_seq":                  [
                                        "tts_utilities", "tts_seq", "tts_html_utils", 
                                        "tts_papertrail", "tts_data_utils", "demosat_data_utils", 
                                        "demosat_dict", "tts_dictionary_interface", "demosat_dictionary_interface", 
                                        "tts_dtat"
                                    ],
    "demosat_tower":                [
                                        "tts_utilities", "tts_html_utils", "tts_papertrail", "tts_data_utils", 
                                        "jpl-time", "tts_tower", "demosat_data_utils", "tts_dtat", "tts_seq", 
                                        "demosat_dict", "tts_dictionary_interface", "tts_fresh", "demosat_fresh", 
                                        "demosat_dictionary_interface", "demosat_seq", "tts_spice"
                                    ],
}


GROUP_MAPPING = {
    "TTS Core": [
        "tts_utilities", "tts_html_utils", "tts_papertrail", "tts_data_utils", 
        "tts_fresh", "tts_dictionary_interface", "tts_seq", 
        "tts_dexter", "tts_dante", "tts_tower"
    ],
    "DemoSat Adaptation": [
        "demosat_data_utils", "demosat_dict", "demosat_dictionary_interface", 
        "demosat_seq", "demosat_fresh"
    ],
    "Other JPL": [
        "jpl-time", "tts_dtat"
    ]
}

IMAGE_NAME_BASE = "clean-test-env"
console = Console()
client = docker.from_env()

# --- Embedded Scripts ---

DOC_CHECKER_SCRIPT = r"""
import ast, os, sys, json, argparse, traceback

class DocChecker(ast.NodeVisitor):
    def __init__(self):
        self.stats = {
            "issues": [],
            "total_items": 0,
            "documented_items": 0
        }
        self.current_file = ""
        self.class_doc_stack = []

    def visit_ClassDef(self, node):
        doc = ast.get_docstring(node)
        self.class_doc_stack.append(doc)
        self.stats["total_items"] += 1
        if doc:
            self.stats["documented_items"] += 1
        else:
            self.stats["issues"].append({
                "file": self.current_file,
                "line": node.lineno,
                "type": "Missing Class Doc",
                "name": node.name,
                "context": "Class Definition"
            })
        self.generic_visit(node)
        self.class_doc_stack.pop()

    def visit_FunctionDef(self, node):
        self._check_func(node)

    def visit_AsyncFunctionDef(self, node):
        self._check_func(node)

    def _check_func(self, node):
        name = node.name
        
        # EXCLUSION: Skip __init__ and setters
        is_init = (name == "__init__")
        if is_init: return

        doc = ast.get_docstring(node)
        is_property = False
        is_setter = False
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == 'property':
                is_property = True
            elif isinstance(dec, ast.Attribute) and dec.attr == 'setter':
                is_setter = True
        if is_setter: return

        target_doc = doc
        # Note: we no longer check is_init here as it returns early above.

        self.stats["total_items"] += 1
        if doc:
            self.stats["documented_items"] += 1
        else:
            issue_type = "Missing Prop Doc" if is_property else "Missing Func Doc"
            context = "Property Definition" if is_property else "Function Definition"
            self.stats["issues"].append({
                "file": self.current_file,
                "line": node.lineno,
                "type": issue_type,
                "name": name,
                "context": context
            })

        args = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
        if node.args.vararg: args.append(node.args.vararg.arg)
        if node.args.kwarg: args.append(node.args.kwarg.arg)
        args = [a for a in args if a not in ['self', 'cls']]
        
        for arg in args:
            self.stats["total_items"] += 1
            if target_doc:
                if arg in target_doc:
                    self.stats["documented_items"] += 1
                else:
                    self.stats["issues"].append({
                        "file": self.current_file, "line": node.lineno, "type": "Missing Arg Doc",
                        "name": arg, "context": f"in {name}(...)"
                    })
            else:
                self.stats["issues"].append({
                    "file": self.current_file, "line": node.lineno, "type": "Missing Arg Doc",
                    "name": arg, "context": f"in {name}(...) (No docstring found)"
                })

def run_check(target_dir):
    try:
        if not os.path.exists(target_dir):
            print(json.dumps({"score": 0, "issues": []}))
            return
        checker = DocChecker()
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d.lower() not in ['test', 'tests']]
            for file in files:
                if file.endswith(".py") and "test" not in file.lower():
                    full_path = os.path.join(root, file)
                    checker.current_file = os.path.relpath(full_path, target_dir)
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            tree = ast.parse(f.read())
                            checker.visit(tree)
                    except Exception: pass
        score = (checker.stats["documented_items"] / checker.stats["total_items"] * 100) if checker.stats["total_items"] > 0 else 0
        print(json.dumps({"score": round(score, 1), "issues": checker.stats["issues"]}))
    except Exception:
        print(json.dumps({"score": 0, "issues": []}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    run_check(args.target)
"""

LOCATE_SCRIPT = """
import sys, os, importlib
try:
    lib_name = sys.argv[1].replace('-', '_')
    m = importlib.import_module(lib_name)
    paths = getattr(m, "__path__", [])
    if paths: print(paths[0])
    elif hasattr(m, "__file__"): print(os.path.dirname(m.__file__))
except Exception as e: print(f"ERROR: {e}")
"""

# --- Helper Functions ---

pypi_cache = {}

def check_pypi_exists(package_name):
    if package_name in INTERNAL_REPO_URLS: return False
    if package_name in pypi_cache: return pypi_cache[package_name]
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        r = requests.get(url, timeout=2)
        exists = (r.status_code == 200)
    except requests.RequestException: exists = False
    pypi_cache[package_name] = exists
    return exists

def copy_file_from_container(container, src_path, dest_path):
    try:
        stream, stat = container.get_archive(src_path)
        file_obj = io.BytesIO()
        for chunk in stream: file_obj.write(chunk)
        file_obj.seek(0)
        with tarfile.open(fileobj=file_obj) as tar:
            tar.extractall(path=os.path.dirname(dest_path))
            extracted_path = os.path.join(os.path.dirname(dest_path), os.path.basename(src_path))
            if os.path.exists(extracted_path) and extracted_path != dest_path:
                 if os.path.exists(dest_path): os.remove(dest_path)
                 os.rename(extracted_path, dest_path)
        return True
    except Exception: return False

def extract_folder_from_container(container, src_path, dest_folder):
    try:
        stream, stat = container.get_archive(src_path)
        file_obj = io.BytesIO()
        for chunk in stream: file_obj.write(chunk)
        file_obj.seek(0)
        with tarfile.open(fileobj=file_obj) as tar:
            tar.extractall(path=dest_folder)
        expected_name = os.path.basename(src_path)
        full_path = os.path.join(dest_folder, expected_name)
        return full_path if os.path.exists(full_path) else None
    except Exception: return None


def generate_mermaid_graph(tested_libs):
    # 1. Calculate relevant nodes
    relevant_nodes = set(tested_libs)
    stack = list(tested_libs)
    while stack:
        node = stack.pop()
        deps = FULL_DEP_GRAPH.get(node, [])
        for dep in deps:
            if dep not in relevant_nodes:
                relevant_nodes.add(dep)
                stack.append(dep)

    # 2. Transitive Reduction
    adj = defaultdict(set)
    for consumer in relevant_nodes:
        providers = FULL_DEP_GRAPH.get(consumer, [])
        for provider in providers:
            if provider in relevant_nodes: adj[provider].add(consumer)

    final_edges = []
    def has_path(start, target, current_adj):
        stack = list(current_adj.get(start, []))
        visited = set()
        while stack:
            node = stack.pop()
            if node == target: return True
            if node not in visited:
                visited.add(node)
                stack.extend(list(current_adj.get(node, [])))
        return False

    for provider in list(adj.keys()):
        consumers = list(adj[provider])
        for consumer in consumers:
            adj[provider].remove(consumer)
            if not has_path(provider, consumer, adj):
                final_edges.append((provider, consumer))
            adj[provider].add(consumer)

    # 3. Sort nodes into Groups
    groups = defaultdict(list)
    for node in relevant_nodes:
        found = False
        for group_name, members in GROUP_MAPPING.items():
            if node in members:
                groups[group_name].append(node)
                found = True
                break
        if not found:
            if node.startswith("tts_") or node == "tts_fresh":
                groups["TTS Core"].append(node)
            elif node.startswith("demosat_"):
                groups["DemoSat Adaptation"].append(node)
            else:
                groups["Other JPL"].append(node)

    # 4. Generate Mermaid
    mermaid_lines = [
        "%%{init: {'theme': 'base', 'flowchart': {'curve': 'stepBefore', 'nodeSpacing': 60, 'rankSpacing': 80}}}%%",
        "graph TB", 
        "    classDef softRed fill:#f28b82,stroke:#c53929,stroke-width:2px,color:#333;",
        "    classDef default fill:#fff,stroke:#333,stroke-width:1px,color:#333;", 
        "    classDef grey fill:#ecf0f1,stroke:#bdc3c7,stroke-width:1px,color:#333;"
    ]

    # Render Groups
    priority_order = ["Other JPL", "TTS Core", "DemoSat Adaptation"]
    sorted_groups = sorted(groups.keys(), key=lambda x: priority_order.index(x) if x in priority_order else 99)

    for group_name in sorted_groups:
        nodes = groups.get(group_name, [])
        if not nodes: continue
        
        mermaid_lines.append(f'    subgraph "{group_name}"')
        mermaid_lines.append(f'      direction TB')
        for node in nodes:
            style_class = ""
            if node not in HIGHLIGHTED_LIBRARIES:
                style_class = ":::grey"
            elif node in INTERNAL_REPO_URLS and not node.startswith("tts"):
                style_class = ":::softRed"
            mermaid_lines.append(f"      {node}{style_class}")
        mermaid_lines.append("    end")

    # Render Edges
    for provider, consumer in final_edges:
        mermaid_lines.append(f"    {provider} --> {consumer}")

    # --- NEW: Invisible "Ghost" Edges to force vertical stacking ---
    if groups["Other JPL"] and groups["TTS Core"]:
         mermaid_lines.append(f"    {groups['Other JPL'][0]} ~~~ {groups['TTS Core'][0]}")
    
    if groups["TTS Core"] and groups["DemoSat Adaptation"]:
         mermaid_lines.append(f"    {groups['TTS Core'][-1]} ~~~ {groups['DemoSat Adaptation'][0]}")

    return "\n".join(mermaid_lines)

def parse_coverage_percent(logs):
    try:
        match = re.search(r'TOTAL\s+.*?(\d+(?:\.\d+)?)%\s*$', logs, re.MULTILINE)
        if match:
            coverage = float(match.group(1))
            if coverage == int(coverage):
                return f"{int(coverage)}%"
            else:
                return f"{coverage:.1f}%"
        neg_match = re.search(r'TOTAL\s+.*?(-\d+(?:\.\d+)?)%\s*$', logs, re.MULTILINE)
        if neg_match:
            return "0%"
        return "N/A"
    except Exception as e:
        print(f"Error parsing coverage: {e}")
        return "Err"

def parse_audit_json(json_str):
    results = []
    try:
        # Find start of JSON object or array
        match = re.search(r'(\{|\[)', json_str)
        if not match:
            return []
            
        start_index = match.start()
        
        # Use raw_decode to parse just the JSON part, ignoring trailing text
        data, _ = json.JSONDecoder().raw_decode(json_str[start_index:])

        # Normalize data structure
        deps = []
        if isinstance(data, list):
            deps = data[0] if (data and isinstance(data[0], list)) else data
        elif isinstance(data, dict):
            deps = data.get("dependencies", [])

        for dep in deps:
            name = dep.get("name")
            version = dep.get("version")
            vulns = dep.get("vulns", [])
            
            for vuln in vulns:
                v_id = vuln.get("id")
                if v_id.startswith("GHSA"):
                    url = f"https://github.com/advisories/{v_id}"
                elif v_id.startswith("PYSEC"):
                    url = f"https://osv.dev/vulnerability/{v_id}"
                else:
                    url = f"https://www.cve.org/CVERecord?id={v_id}"
                
                results.append({
                    "name": name, 
                    "version": version, 
                    "id": v_id, 
                    "url": url, 
                    "fix_versions": ", ".join(vuln.get("fix_versions", []))
                })
    except Exception as e: 
        print(f"JSON Parse Error: {e}")
        return []
    return results

# --- Main Execution ---

def run_matrix(target_versions, target_graph):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_root = os.path.abspath(f"test_matrix_report_{timestamp}")
    details_root = os.path.join(report_root, "details")
    os.makedirs(details_root, exist_ok=True)
    console.print(f"[bold green]Report directory created at: {report_root}[/]")

    results = {}
    sorted_target_versions = sorted(target_versions, key=lambda x: [int(c) if c.isdigit() else c for c in x.split('.')])

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        overall_task = progress.add_task("Isolation Testing...", total=len(sorted_target_versions))

        for version in sorted_target_versions:
            results[version] = {}
            base_tag = f"{IMAGE_NAME_BASE}:{version}"
            ssh_key_path = os.path.expanduser("~/.ssh/id_rsa")
            try:
                with open(ssh_key_path, "rb") as f: ssh_key_b64 = base64.b64encode(f.read()).decode('utf-8')
            except:
                console.print(f"[bold red]SSH key not found at {ssh_key_path}[/]"); return

            progress.update(overall_task, description=f"Ensuring Base Py {version}...")

            client.images.build(path=".", tag=base_tag, dockerfile=Path(__file__).parent.joinpath("dockerfiles/Dockerfile.unittest"), buildargs={"PYTHON_VERSION": version, "SSH_KEY_B64": ssh_key_b64}, rm=True)

            for lib_name, deps in target_graph.items():
                progress.update(overall_task, description=f"Py {version} -> {lib_name}...")
                try:
                    start_time = datetime.datetime.now()
                    container = client.containers.run(base_tag, command="tail -f /dev/null", detach=True)
                    
                    # Install Steps
                    install_cmds = [f"pip install --no-build-isolation {d}" for d in BUILD_DEPS]
                    for d in deps:
                        if d in INTERNAL_REPO_URLS: install_cmds.append(f"pip install --no-build-isolation {INTERNAL_REPO_URLS[d]}")
                    
                    target_install = f"pip install --no-build-isolation {INTERNAL_REPO_URLS[lib_name]}"
                    install_res = container.exec_run(f"sh -c '{' && '.join(install_cmds + [target_install])}'")
                    install_logs = install_res.output.decode('utf-8', errors='replace')

                    for script_name, content in [("bandit.yaml", "assert_used:\n  skips: ['*/test/*', '*/tests/*']\n"), ("doc_checker.py", DOC_CHECKER_SCRIPT), ("locate_lib.py", LOCATE_SCRIPT)]:
                        b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
                        container.exec_run(f"sh -c 'echo {b64} | base64 -d > /tmp/{script_name}'")

                    container.exec_run("sh -c 'pip freeze > /tmp/freeze.txt'")
                    
                    test_res = container.exec_run(f"pytest --cov={lib_name} --cov-report=term --cov-report=html:/tmp/cov_html --pyargs {lib_name}.test")
                    test_logs = test_res.output.decode('utf-8', errors='replace')
                    
                    audit_res = container.exec_run("pip-audit -f json")
                    audit_output = audit_res.output.decode('utf-8', errors='replace')
                    
                    # FIX: Audit exit code 1 means "vulnerabilities found", which is a valid run.
                    audit_tool_ran_successfully = audit_res.exit_code in [0, 1]
                    
                    path_res = container.exec_run(f"python3 /tmp/locate_lib.py {lib_name}")
                    install_path = path_res.output.decode('utf-8', errors='replace').strip()

                    if "ERROR" in install_path or not install_path:
                        bandit_success, bandit_logs, doc_score, doc_issues = False, "Locate failed", 0, []
                    else:
                        bandit_res = container.exec_run(f'sh -c "bandit -c /tmp/bandit.yaml -r {install_path}"')
                        bandit_success, bandit_logs = bandit_res.exit_code == 0, bandit_res.output.decode('utf-8', errors='replace')
                        doc_res = container.exec_run(f"python3 /tmp/doc_checker.py --target {install_path}")
                        doc_score, doc_issues = 0, []
                        try:
                            doc_data = json.loads(doc_res.output.decode('utf-8', errors='replace'))
                            doc_score, doc_issues = doc_data.get("score", 0), doc_data.get("issues", [])
                        except json.decoder.JSONDecodeError:
                            doc_score, doc_issues = -1, []

                    lib_detail_dir = os.path.join(details_root, version, lib_name)
                    os.makedirs(lib_detail_dir, exist_ok=True)
                    cov_pct = parse_coverage_percent(test_logs)
                    extracted_path = extract_folder_from_container(container, "/tmp/cov_html", lib_detail_dir)
                    if extracted_path:
                        final_cov = os.path.join(lib_detail_dir, "coverage")
                        if os.path.exists(final_cov): shutil.rmtree(final_cov)
                        os.rename(extracted_path, final_cov)
                    
                    copy_file_from_container(container, "/tmp/freeze.txt", os.path.join(lib_detail_dir, "freeze.txt"))
                    freeze_content = open(os.path.join(lib_detail_dir, "freeze.txt")).read() if os.path.exists(os.path.join(lib_detail_dir, "freeze.txt")) else ""
                    
                    container_logs_raw = container.logs().decode('utf-8', errors='replace')
                    full_combined_logs = f"=== INSTALLATION OUTPUT ===\n{install_logs}\n\n=== DOCKER DAEMON LOGS ===\n{container_logs_raw}"

                    container.remove(force=True)
                    
                    audit_findings = parse_audit_json(audit_output)
                    
                    render_detail_page(os.path.join(lib_detail_dir, "index.html"), lib_name, version, test_res.exit_code == 0, audit_tool_ran_successfully, bandit_success, test_logs, audit_findings, audit_output, bandit_logs, freeze_content, generate_mermaid_graph([lib_name]), cov_pct, bool(extracted_path), doc_score, doc_issues, full_combined_logs)

                    results[version][lib_name] = {
                        "test_success": test_res.exit_code == 0, 
                        "audit_success": audit_tool_ran_successfully, 
                        "vulns_found": len(audit_findings) > 0, # Track finding status separately
                        "bandit_success": bandit_success, 
                        "duration": f"{(datetime.datetime.now() - start_time).total_seconds():.1f}s", 
                        "coverage": cov_pct, 
                        "doc_score": doc_score, 
                        "detail_link": f"details/{version}/{lib_name}/index.html"
                    }
                except Exception as e:
                    results[version][lib_name] = {"error": str(e), "test_success": False, "audit_success": False, "vulns_found": False, "bandit_success": False, "duration": "0s", "coverage": "Err", "doc_score": 0, "detail_link": "#"}
            progress.advance(overall_task)

    render_main_report(results, generate_mermaid_graph(target_graph.keys()), report_root, timestamp)

# --- Templates ---

MAIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Isolation Test Matrix Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; background-color: #f4f7f6; color: #333; }
        h1, h2 { color: #2c3e50; }
        .timestamp { color: #7f8c8d; font-size: 0.9em; margin-bottom: 30px; }
        .graph-container { background: white; padding: 20px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); text-align: center; }
        .version-card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .version-header { border-bottom: 2px solid #eee; margin-bottom: 15px; padding-bottom: 10px; }
        .status-badge { padding: 4px 8px; border-radius: 4px; font-size: 0.75em; font-weight: bold; text-transform: uppercase; color: white; display: inline-block; min-width: 50px; text-align: center; cursor: pointer; transition: transform 0.1s ease; text-decoration: none; }
        .status-badge:hover { transform: scale(1.05); filter: brightness(1.1); }
        .pass { background-color: #27ae60; } .fail { background-color: #e74c3c; } .warn { background-color: #f39c12; } .err { background-color: #95a5a6; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; background: #f8f9fa; padding: 12px; border-bottom: 2px solid #dee2e6; font-size: 0.9em; color: #7f8c8d; }
        td { padding: 12px; border-bottom: 1px solid #eee; vertical-align: middle; }
        .cov-link, .doc-link { color: #2980b9; text-decoration: none; border-bottom: 1px dotted #2980b9; font-weight: bold; }
        .cov-link:hover, .doc-link:hover { color: #1abc9c; border-bottom: 1px solid #1abc9c; }
        .action-link { color: #3498db; text-decoration: none; font-weight: 600; border: 1px solid #3498db; padding: 4px 10px; border-radius: 4px; font-size: 0.9em; }
    </style>
</head>
<body>
    <h1>Library Isolation Test Matrix</h1>
    <div class="timestamp">Generated on {{ timestamp }}</div>
    <div class="graph-container"><h2>Dependency Topology</h2><div class="mermaid">{{ mermaid_content }}</div></div>
    {% for version, libs in results.items() %}
    <div class="version-card">
        <div class="version-header"><h2>Python {{ version }}</h2></div>
        <table>
            <thead><tr><th>Library</th><th>Test</th><th>Pip Audit</th><th>Bandit</th><th>Docs</th><th>Coverage</th><th>Time</th><th>Artifacts</th></tr></thead>
            <tbody>
                {% for lib_name, data in libs.items() %}
                <tr>
                    <td><strong>{{ lib_name }}</strong></td>
                    <td><a href="{{ data.detail_link }}#logs">{% if 'error' in data %}<span class="status-badge err">ERR</span>{% elif data.test_success %}<span class="status-badge pass">PASS</span>{% else %}<span class="status-badge fail">FAIL</span>{% endif %}</a></td>
                    <td><a href="{{ data.detail_link }}#audit">{% if 'error' in data %}<span class="status-badge err">-</span>{% elif not data.audit_success %}<span class="status-badge fail">ERR</span>{% elif data.vulns_found %}<span class="status-badge warn">VULN</span>{% else %}<span class="status-badge pass">PASS</span>{% endif %}</a></td>
                    <td><a href="{{ data.detail_link }}#bandit">{% if 'error' in data %}<span class="status-badge err">-</span>{% elif data.bandit_success %}<span class="status-badge pass">PASS</span>{% else %}<span class="status-badge fail">FAIL</span>{% endif %}</a></td>
                    <td><a href="{{ data.detail_link }}#docs" class="doc-link" style="color: {{ '#27ae60' if data.doc_score >= 90 else '#f39c12' if data.doc_score > 50 else '#e74c3c' }};">{% if data.doc_score < 0 %}N/A{% else %}{{ data.doc_score }}%{% endif %}</a></td>
                    <td>{% if data.coverage != "N/A" and data.coverage != "Err" %}<a href="{{ data.detail_link }}#coverage" class="cov-link" style="color: {{ '#27ae60' if data.coverage.rstrip('%')|float >= 80 else '#f39c12' if data.coverage.rstrip('%')|float >= 50 else '#e74c3c' }};">{{ data.coverage }}</a>{% else %}{{ data.coverage }}{% endif %}</td>
                    <td style="font-family: monospace;">{{ data.duration }}</td>
                    <td>{% if data.detail_link != "#" %}<a href="{{ data.detail_link }}" target="_blank" class="action-link">View Artifacts &rarr;</a>{% else %}<span style="color: #e74c3c;">{{ data.error }}</span>{% endif %}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endfor %}
    <script type="module">import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs'; mermaid.initialize({ startOnLoad: true, theme: 'base' });</script>
</body>
</html>
"""

DETAIL_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ lib_name }} - Py{{ version }} Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background-color: #f4f7f6; display: flex; flex-direction: column; min-height: 100vh; }
        header { background: white; padding: 20px 40px; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; }
        .status-badge { padding: 5px 12px; border-radius: 4px; color: white; font-weight: bold; text-transform: uppercase; margin-left: 5px; }
        .pass { background-color: #27ae60; } .fail { background-color: #e74c3c; } .warn { background-color: #f39c12; }
        .container { flex: 1; padding: 30px; max-width: 1200px; margin: 0 auto; width: 100%; box-sizing: border-box; }
        .tabs { display: flex; margin-bottom: 20px; border-bottom: 2px solid #ddd; }
        .tab { padding: 10px 20px; cursor: pointer; font-weight: 600; color: #7f8c8d; border-bottom: 3px solid transparent; }
        .tab.active { border-bottom-color: #3498db; color: #3498db; }
        .tab-content { display: none; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); padding: 20px; }
        .tab-content.active { display: block; }
        pre { background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto; font-family: 'Courier New', monospace; font-size: 0.9em; white-space: pre-wrap; }
        table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
        th { text-align: left; background: #eee; padding: 10px; }
        td { padding: 10px; border-bottom: 1px solid #eee; }
        .cta-button { display: inline-block; background-color: #3498db; color: white; padding: 12px 24px; border-radius: 5px; text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
    <header>
        <div><h1>{{ lib_name }} / Python {{ version }}</h1></div>
        <div>
            <span class="status-badge {{ 'pass' if test_success else 'fail' }}">Tests: {{ 'PASS' if test_success else 'FAIL' }}</span>
            <span class="status-badge" style="background-color: {{ '#27ae60' if doc_score >= 90 else '#f39c12' if doc_score > 50 else '#e74c3c' }};">Docs: {% if doc_score < 0 %}N/A{% else %}{{ doc_score }}%{% endif %}</span>
            {% if cov_pct != "N/A" and cov_pct != "Err" %}
            <span class="status-badge" style="background-color: {{ '#27ae60' if cov_pct.rstrip('%')|float >= 80 else '#f39c12' if cov_pct.rstrip('%')|float >= 50 else '#e74c3c' }};">Coverage: {{ cov_pct }}</span>
            {% endif %}
        </div>
    </header>
    <div class="container">
        <div class="tabs">
            <div class="tab active" data-target="logs" onclick="openTab('logs')">Test Logs</div>
            <div class="tab" data-target="full-logs" onclick="openTab('full-logs')">Container & Setup</div>
            <div class="tab" data-target="audit" onclick="openTab('audit')">Pip Audit</div>
            <div class="tab" data-target="docs" onclick="openTab('docs')">Doc Analysis</div>
            <div class="tab" data-target="bandit" onclick="openTab('bandit')">Bandit Scan</div>
            <div class="tab" data-target="freeze" onclick="openTab('freeze')">Pip Freeze</div>
            {% if has_cov_report %}<div class="tab" data-target="coverage" onclick="openTab('coverage')">Coverage</div>{% endif %}
        </div>
        <div id="logs" class="tab-content active"><h3>Pytest Output</h3><pre>{{ logs }}</pre></div>
        <div id="full-logs" class="tab-content"><h3>Container & Setup Logs</h3><pre>{{ full_logs }}</pre></div>
        
        <div id="audit" class="tab-content">
            <h3>Pip Audit</h3>
            {% if not audit_success %}
                <p style="color: #e74c3c;"><strong>Error: Pip Audit Failed to Run</strong></p>
                <p>The tool returned an unexpected exit code (not 0 or 1). See raw output below:</p>
                <pre>{{ audit_raw }}</pre>
            {% elif audit_data %}
                <p style="color: #f39c12;"><strong>Warning: Vulnerabilities Found</strong></p>
                <table><thead><tr><th>Package</th><th>Version</th><th>ID</th><th>Fixed In</th></tr></thead>
                <tbody>{% for item in audit_data %}<tr><td>{{ item.name }}</td><td>{{ item.version }}</td><td><a href="{{ item.url }}">{{ item.id }}</a></td><td>{{ item.fix_versions }}</td></tr>{% endfor %}</tbody></table>
            {% else %}
                <p style="color: #27ae60;">No vulnerabilities found.</p>
            {% endif %}
        </div>
        <div id="docs" class="tab-content">
            <h3>Doc Coverage: {% if doc_score < 0 %}N/A{% else %}{{ doc_score }}%{% endif %}</h3>
            {% if doc_score < 0 %}
            <p style="color: #e74c3c;">Documentation analysis failed or not available.</p>
            {% elif doc_issues %}
            <table><thead><tr><th>Location</th><th>Type</th><th>Name</th><th>Context</th></tr></thead>
            <tbody>{% for issue in doc_issues %}<tr><td>{{ issue.file }}:{{ issue.line }}</td><td>{{ issue.type }}</td><td><code>{{ issue.name }}</code></td><td>{{ issue.context }}</td></tr>{% endfor %}</tbody></table>
            {% else %}<p style="color: #27ae60;">Perfect documentation!</p>{% endif %}
        </div>
        <div id="bandit" class="tab-content"><h3>Bandit Scan</h3><pre>{{ bandit_logs }}</pre></div>
        <div id="freeze" class="tab-content"><h3>Pip Freeze</h3><pre>{{ freeze }}</pre></div>
        {% if has_cov_report %}<div id="coverage" class="tab-content" style="text-align: center;"><h3>Coverage Report: <span style="color: {{ '#27ae60' if cov_pct.rstrip('%')|float >= 80 else '#f39c12' if cov_pct.rstrip('%')|float >= 50 else '#e74c3c' }};">{{ cov_pct }}</span></h3><a href="coverage/index.html" target="_blank" class="cta-button">Open Full Report &rarr;</a></div>{% endif %}
    </div>
    <script>
        function openTab(t) {
            document.querySelectorAll('.tab-content').forEach(e => e.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(e => e.classList.remove('active'));
            document.getElementById(t).classList.add('active');
            document.querySelector(`.tab[data-target="${t}"]`).classList.add('active');
        }
        window.onload = () => { const h = window.location.hash.substring(1); if(h) openTab(h); };
    </script>
</body>
</html>
"""

def render_main_report(results, mermaid, root, ts):
    html = Template(MAIN_TEMPLATE).render(results=results, mermaid_content=mermaid, timestamp=ts)
    with open(os.path.join(root, "index.html"), "w") as f: f.write(html)
    try: import webbrowser; webbrowser.open(f"file://{os.path.join(root, 'index.html')}")
    except: pass


def render_detail_page(path, lib, ver, ts, aus, bs, logs, aud, aur, bl, fr, mer, cp, hcr, ds, di, full_logs):
    html = Template(DETAIL_TEMPLATE).render(lib_name=lib, version=ver, test_success=ts, audit_success=aus, bandit_success=bs, logs=logs, audit_data=aud, audit_raw=aur, bandit_logs=bl, freeze=fr, mermaid_content=mer, cov_pct=cp, has_cov_report=hcr, doc_score=ds, doc_issues=di, full_logs=full_logs)
    with open(path, "w") as f: f.write(html)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", "-p", nargs="+", help="Python versions to test (e.g., 3.8 3.9 3.10)")
    parser.add_argument("--libs", "-l", nargs="+", help="Libraries to test (supports wildcards like demo*)")
    run_args = parser.parse_args()
    v = run_args.python if run_args.python else DEFAULT_PYTHON_VERSIONS
    
    # Handle wildcard expansion for library names
    if run_args.libs:
        matched_libs = set()
        for pattern in run_args.libs:
            # Check if pattern contains wildcard characters
            if '*' in pattern or '?' in pattern or '[' in pattern:
                # Match pattern against all available libraries
                matches = [lib for lib in FULL_DEP_GRAPH.keys() if fnmatch.fnmatch(lib, pattern)]
                if matches:
                    matched_libs.update(matches)
                else:
                    print(f"Warning: Pattern '{pattern}' did not match any libraries", file=sys.stderr)
            else:
                # Direct match (no wildcard)
                if pattern in FULL_DEP_GRAPH:
                    matched_libs.add(pattern)
                else:
                    print(f"Warning: Library '{pattern}' not found in dependency graph", file=sys.stderr)
        
        # Build the filtered dependency graph
        l = {lib: FULL_DEP_GRAPH[lib] for lib in matched_libs}
        
        if not l:
            print("Error: No valid libraries matched. Available libraries:", file=sys.stderr)
            print(", ".join(sorted(FULL_DEP_GRAPH.keys())), file=sys.stderr)
            sys.exit(1)
    else:
        l = FULL_DEP_GRAPH
    
    run_matrix(v, l)