import os
import shutil
import tempfile
import subprocess
import argparse
import re
import sys
from pathlib import Path
from git import Repo, GitCommandError
from jinja2 import Template
import toml
from packaging import version

from tts_utilities.logger import create_logger

logger = create_logger(name='tts_deployments.git_report')

# --- READTHEDOCS STYLE TEMPLATE ---
# --- READTHEDOCS STYLE TEMPLATE (LOCAL ASSETS) ---
RTD_TEMPLATE = """
<!DOCTYPE html>
<html class="writer-html5" lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ repo_name }} Documentation Portal</title>
    
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css" />
    
    <style>
        :root {
            color-scheme: light;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #1f2937;
            background: #f3f4f6;
        }

        * { box-sizing: border-box; }
        body { margin: 0; }
        .wy-grid-for-nav { min-height: 100vh; display: flex; }
        .wy-nav-side { width: 260px; flex: 0 0 260px; background: #172033; color: #fff; }
        .wy-side-scroll { position: sticky; top: 0; padding: 28px 22px; }
        .wy-side-nav-search a { color: #fff; font-size: 1.1rem; font-weight: 700; text-decoration: none; }
        .wy-side-nav-search .version { color: #a9b7cf; margin-top: 8px; }
        .wy-menu { margin-top: 36px; }
        .wy-menu .caption-text { color: #a9b7cf; font-size: .8rem; text-transform: uppercase; letter-spacing: .08em; }
        .wy-menu ul { list-style: none; margin: 12px 0 0; padding: 0; }
        .wy-menu li { margin: 8px 0; }
        .wy-menu a { color: #e5e7eb; text-decoration: none; }
        .wy-menu a:hover { color: #fff; text-decoration: underline; }
        .wy-nav-content-wrap { flex: 1; min-width: 0; }
        .wy-nav-content { max-width: 1100px; margin: 0 auto; padding: 48px 56px; }
        .wy-breadcrumbs { list-style: none; margin: 0; padding: 0; color: #6b7280; }
        .wy-breadcrumbs li { display: inline; }
        .rst-content hr { border: 0; border-top: 1px solid #d1d5db; margin: 18px 0 42px; }
        .document h1 { font-size: clamp(2rem, 5vw, 3.25rem); line-height: 1.1; margin: 0 0 16px; color: #111827; }
        .document h2 { color: #1f2937; margin-top: 0; }
        .document > p { color: #6b7280; font-size: 1.1rem; margin-bottom: 42px; }
        footer { color: #6b7280; margin-top: 56px; }
        
        .wy-nav-content { max-width: 1100px; margin: 0 auto; }
        
        /* The version grid layout */
        .version-section { margin-bottom: 2.5rem; }
        .version-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); 
            gap: 20px; 
            margin-top: 15px; 
        }
        
        /* Card Styling */
        .version-card { 
            background: #fff; 
            border: 1px solid #e1e4e5; 
            border-radius: 4px; 
            padding: 18px; 
            text-decoration: none !important; 
            color: #404040; 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            transition: all 0.2s ease;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }

        .version-card:hover { 
            border-color: #2980b9; 
            transform: translateY(-2px); 
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            color: #2980b9;
        }
        
        .version-card .fa { color: #d9d9d9; transition: color 0.2s; }
        .version-card:hover .fa { color: #2980b9; }
        
        /* Highlight Latest */
        .version-card.latest { 
            border-left: 5px solid #2980b9; 
            background: #fcfcfc; 
        }
        
        /* Hide the search bar on the portal page */
        .wy-side-nav-search input { display: none; }
    </style>
</head>

<body class="wy-body-for-nav">
  <div class="wy-grid-for-nav">
    
    <nav data-toggle="wy-nav-shift" class="wy-nav-side">
      <div class="wy-side-scroll">
        <div class="wy-side-nav-search">
          <a href="#" class="icon icon-home"> {{ repo_name }}</a>
          <div class="version">Portal</div>
        </div>
        <div class="wy-menu wy-menu-vertical">
          <p class="caption" role="heading"><span class="caption-text">Quick Links</span></p>
          <ul>
            {% if latest_tag %}
            <li class="toctree-l1"><a class="reference internal" href="latest/index.html">Latest Release ({{ latest_tag }})</a></li>
            {% endif %}
            <li class="toctree-l1"><a class="reference internal" href="#branches">Active Development</a></li>
            <li class="toctree-l1"><a class="reference internal" href="#releases">Release History</a></li>
          </ul>
        </div>
      </div>
    </nav>

    <section data-toggle="wy-nav-shift" class="wy-nav-content-wrap">
      
      <nav class="wy-nav-top" aria-label="Mobile navigation menu">
         <i data-toggle="wy-nav-top" class="fa fa-bars"></i>
         <a href="#">{{ repo_name }}</a>
      </nav>

      <div class="wy-nav-content">
        <div class="rst-content">
          
          <div role="navigation" aria-label="Page navigation">
              <ul class="wy-breadcrumbs">
                  <li><a href="#" class="icon icon-home"></a> &raquo;</li>
                  <li>Documentation Overview</li>
              </ul>
              <hr/>
          </div>

          <div role="main" class="document">
            <h1>{{ repo_name }} Documentation</h1>
            <p style="font-size: 1.1em; color: #666; margin-bottom: 2em;">Select a version below to view the documentation.</p>
            
            {% if latest_tag %}
            <div class="version-section">
                <h2><i class="fa fa-star" style="font-size: 0.8em; color: #f1c40f;"></i> Latest Stable</h2>
                <div class="version-grid">
                    <a href="latest/index.html" class="version-card latest">
                        <span>Version {{ latest_tag }}</span>
                        <i class="fa fa-arrow-right"></i>
                    </a>
                </div>
            </div>
            {% endif %}

            {% if branches %}
            <div class="version-section" id="branches">
                <h2><i class="fa fa-code-branch" style="font-size: 0.8em; color: #95a5a6;"></i> Active Branches</h2>
                <div class="version-grid">
                    {% for branch in branches %}
                    <a href="{{ branch|replace('/', '_') }}/index.html" class="version-card">
                        <span>{{ branch }}</span>
                        <i class="fa fa-folder"></i>
                    </a>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
            
            {% if tags %}
            <div class="version-section" id="releases">
                <h2><i class="fa fa-tag" style="font-size: 0.8em; color: #95a5a6;"></i> Release History</h2>
                <div class="version-grid">
                    {% for tag in tags %}
                    <a href="{{ tag }}/index.html" class="version-card">
                        <span>{{ tag }}</span>
                        <i class="fa fa-book"></i>
                    </a>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
          </div>

          <footer>
             <hr/>
             <div role="contentinfo"><p>&copy; Generated by tts-deployments.</p></div>
          </footer>
        </div>
      </div>
    </section>
  </div>

</body>
</html>
"""

def get_project_metadata(repo_path):
    """Extract name and version from pyproject.toml."""
    metadata = {"name": repo_path.name, "version": "unknown"}
    pyproject_path = Path(repo_path) / "pyproject.toml"
    if pyproject_path.exists():
        try:
            data = toml.load(pyproject_path)
            metadata["name"] = (data.get("project", {}).get("name") or 
                               data.get("tool", {}).get("poetry", {}).get("name") or 
                               repo_path.name)
            metadata["version"] = (data.get("project", {}).get("version") or 
                                  data.get("tool", {}).get("poetry", {}).get("version") or 
                                  "unknown")
        except Exception: pass
    return metadata

def should_ignore(ref_name, ignore_patterns):
    for pattern in ignore_patterns:
        try:
            if re.fullmatch(pattern, ref_name): return True
        except re.error: pass
    return False

def find_actual_package(repo_path):
    """Finds the inner package directory to avoid 'src' prefix in docs."""
    src_path = repo_path / "src"
    if src_path.exists() and src_path.is_dir():
        for child in src_path.iterdir():
            if child.is_dir() and (child / "__init__.py").exists():
                return child, src_path 
    
    exclude = {'.git', 'docs', 'tests', 'ci', 'build', 'dist', 'venv', '.venv'}
    for child in repo_path.iterdir():
        if child.is_dir() and child.name not in exclude and (child / "__init__.py").exists():
            return child, repo_path

    return repo_path, repo_path

def post_process_api_docs(api_dir):
    """
    1. Removes ' package' suffix from MAIN file titles (fixes parent 'Subpackages' lists).
    2. Removes ' module' suffix from Submodule headers.
    3. Demotes Submodule headers to Level 3 ('^') for indentation.
    """
    for rst_file in api_dir.glob("*.rst"):
        content = rst_file.read_text()

        # --- PASS 1: Main Title Cleanup ---
        content = re.sub(
            r'^(.+?)( package)\n(=+)$',
            lambda m: f"{m.group(1)}\n{'=' * len(m.group(1))}",
            content,
            count=1,
            flags=re.MULTILINE
        )
        
        # --- PASS 2: Submodule Section Cleanup ---
        if "Submodules\n----------" in content:
            parts = content.split("Submodules\n----------")
            preamble = parts[0] + "Submodules\n----------"
            body = parts[1]
            
            pattern = re.compile(r'^(.+?)( module)\n(-+)$', re.MULTILINE)
            
            def replacement(match):
                clean_title = match.group(1) 
                new_underline = '^' * len(clean_title)
                return f"{clean_title}\n{new_underline}"
            
            new_body = pattern.sub(replacement, body)
            content = preamble + new_body

        rst_file.write_text(content)

def generate_dynamic_docs(
    repo_path,
    docs_dir,
    project_name,
    generate_api=True,
    generate_index=True,
):
    """Generate optional API and index sources for a documentation build."""
    package_dir, import_root = find_actual_package(repo_path)
    output_path = repo_path / docs_dir / "api"

    if generate_api:
        if not package_dir.exists():
            logger.warning("Could not find package source, skipping apidoc.")
            return import_root

        if output_path.exists():
            shutil.rmtree(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        exclusions = [
            str(package_dir / "test"),
            str(package_dir / "tests"),
            "setup.py",
            "*migrations*",
        ]

        cmd = [
            "sphinx-apidoc", "-f", "-M",
            "-o", str(output_path),
            str(package_dir),
        ] + exclusions

        subprocess.run(cmd, check=True, capture_output=True)
        post_process_api_docs(output_path)

    if generate_index:
        index_rst = f"""
{project_name}
{'=' * len(project_name)}

Welcome to the documentation for **{project_name}**.

.. note::
   This documentation was automatically generated from source code.

API Reference
-------------
.. toctree::
   :maxdepth: 3
   :glob:

   api/{package_dir.name}

Indices and tables
------------------
* :ref:`genindex`
* :ref:`modindex`
"""
        (repo_path / docs_dir / "index.rst").write_text(index_rst)

    return import_root


def cleanup_generated_docs(repo, repo_path, docs_dir, generated_api=True, generated_index=True):
    if generated_api:
        api_dir = repo_path / docs_dir / "api"
        if api_dir.exists():
            shutil.rmtree(api_dir)

    index_file = repo_path / docs_dir / "index.rst"
    if index_file.exists():
        try:
            repo.git.checkout(str(index_file))
        except GitCommandError:
            if generated_index:
                index_file.unlink()


def _build_sphinx_source(
    repo_path,
    docs_dir,
    output_dir,
    builder="html",
    force_theme=True,
    generate_api=True,
    generate_index=True,
):
    import_root = generate_dynamic_docs(
        repo_path,
        docs_dir,
        get_project_metadata(repo_path)["name"],
        generate_api=generate_api,
        generate_index=generate_index,
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(import_root) + os.pathsep + env.get("PYTHONPATH", "")

    build_cmd = ["sphinx-build", "-b", builder, docs_dir, str(output_dir)]
    if force_theme:
        build_cmd.extend(["-D", "html_theme=sphinx_rtd_theme"])

    subprocess.run(
        build_cmd,
        cwd=repo_path,
        check=True,
        capture_output=True,
        env=env,
    )


def build_current_version(
    repo_path,
    docs_dir="docs",
    output_dir=None,
    builder="html",
    check_dirty=True,
    force_theme=True,
    generate_api=True,
    generate_index=True,
):
    """Build documentation for the current checkout without publishing."""
    repo_path = Path(repo_path)
    repo = Repo(repo_path)
    if check_dirty and repo.is_dirty():
        raise RuntimeError("Git repo dirty.")

    output_dir = Path(output_dir or repo_path / "_build" / "html")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    index_file = repo_path / docs_dir / "index.rst"
    original_index = index_file.read_bytes() if index_file.exists() else None
    try:
        _build_sphinx_source(
            repo_path,
            docs_dir,
            output_dir,
            builder=builder,
            force_theme=force_theme,
            generate_api=generate_api,
            generate_index=generate_index,
        )
    finally:
        cleanup_generated_docs(
            repo,
            repo_path,
            docs_dir,
            generated_api=generate_api,
            generated_index=generate_index,
        )
        if original_index is not None:
            index_file.write_bytes(original_index)
        elif index_file.exists():
            index_file.unlink()
    return output_dir


def build_all_versions(
    repo_path,
    docs_dir="docs",
    builder="html",
    push=False,
    check_dirty=True,
    force_theme=True,
    ignore_errors=True,
    generate_api=True,
    generate_index=True,
):
    repo_path = Path(repo_path)
    repo = Repo(repo_path)
    meta = get_project_metadata(repo_path)
    
    if check_dirty and repo.is_dirty():
        raise RuntimeError("Git repo dirty.")

    try: original_ref = repo.active_branch.name
    except: original_ref = repo.head.commit.hexsha

    ignore_patterns = []
    if (repo_path / 'ci/sphinx_ignore_tags.txt').exists():
        ignore_patterns = (repo_path / 'ci/sphinx_ignore_tags.txt').read_text().splitlines()

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_output_dir = Path(temp_dir_str)
        all_refs = list(repo.tags) + [b for b in repo.heads if b.name != 'gh-pages']
        
        for ref in all_refs:
            if should_ignore(ref.name, ignore_patterns): continue
            
            logger.info(f"🔨 Building docs for {ref.name}...")
            
            repo.git.checkout(ref.name, force=True)
            
            if not (repo_path / docs_dir).exists(): continue

            (repo_path / docs_dir / "_static").mkdir(parents=True, exist_ok=True)
            version_output = temp_output_dir / ref.name.replace('/', '_')
            
            try:
                logger.info(f"Building documentation for {ref.name} in {version_output}")
                _build_sphinx_source(
                    repo_path,
                    docs_dir,
                    version_output,
                    builder=builder,
                    force_theme=force_theme,
                    generate_api=generate_api,
                    generate_index=generate_index,
                )
                logger.info(f"Documentation for {ref.name} built successfully in {version_output}")
            except subprocess.CalledProcessError as e:
                error_output = e.stderr.decode()
                logger.error(f"Failed build on {ref.name}: {error_output}")
                
                # Check for common syntax errors that should be ignored
                if ignore_errors and (
                    "f-string: unmatched" in error_output or 
                    "Configuration error" in error_output or
                    "syntax error" in error_output
                ):
                    logger.warning(f"Ignoring syntax error in {ref.name} and continuing with other versions")
                    continue
                elif ignore_errors:
                    logger.warning(f"Ignoring error in {ref.name} and continuing with other versions")
                    continue
                else:
                    raise RuntimeError(f"Build failed for {ref.name} and ignore_errors is False")
            
            cleanup_generated_docs(
                repo,
                repo_path,
                docs_dir,
                generated_api=generate_api,
                generated_index=generate_index,
            )

        if "gh-pages" in repo.heads:
            logger.info("Checking out existing gh-pages branch")
            repo.git.checkout("gh-pages")
            logger.info("Cleaning existing gh-pages branch content")
            for p in repo_path.iterdir():
                if p.name != ".git":
                    if p.is_dir(): shutil.rmtree(p)
                    else: p.unlink()
        else:
            logger.info("Creating new gh-pages branch")
            repo.git.checkout('--orphan', 'gh-pages')
            repo.git.rm('-rf', '.')
            logger.info("Created new gh-pages branch")

        # Define branch and tag lists for reporting
        display_branches = [b.name for b in repo.heads if b.name != 'gh-pages' and not should_ignore(b.name, ignore_patterns)]
        display_tags = sorted([t.name for t in repo.tags if not should_ignore(t.name, ignore_patterns)], key=version.parse, reverse=True)
        
        built_tags = []
        logger.info("Copying built documentation to gh-pages branch")
        for v_dir in temp_output_dir.iterdir():
            logger.info(f"Copying {v_dir} to {repo_path / v_dir.name}")
            shutil.copytree(v_dir, repo_path / v_dir.name)
            if v_dir.name in [t.name for t in repo.tags]: built_tags.append(v_dir.name)
        logger.info(f"Copied documentation for {len(built_tags)} tags and {len(display_branches)} branches")

        latest_tag = None
        if built_tags:
            latest_tag = sorted(built_tags, key=version.parse)[-1]
            shutil.copytree(repo_path / latest_tag, repo_path / "latest")

        (repo_path / ".nojekyll").write_text("")
        
        # --- RENDER RTD PORTAL ---
        template = Template(RTD_TEMPLATE)
        # display_branches and display_tags are already defined above

        (repo_path / "index.html").write_text(template.render(
            repo_name=meta["name"], current_version=meta["version"], latest_tag=latest_tag,
            branches=display_branches, tags=display_tags
        ))

        repo.git.add(A=True)
        if repo.is_dirty():
            repo.index.commit("Docs update")
            if push: 
                logger.info("Pushing to origin/gh-pages...")
                repo.remotes.origin.push("gh-pages", force=True)

    repo.git.checkout(original_ref)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--docs-dir", default="docs")
    parser.add_argument("--no-force-theme", action="store_true", help="Do not override html_theme in sphinx-build")
    parser.add_argument("--no-generate-api", action="store_true")
    parser.add_argument("--no-generate-index", action="store_true")
    parser.add_argument("--no-ignore-errors", action="store_true", help="Do not ignore syntax errors in conf.py and other files")
    args = parser.parse_args()

    build_all_versions(
        Path.cwd(),
        docs_dir=args.docs_dir,
        push=args.push,
        force_theme=not args.no_force_theme,
        ignore_errors=not args.no_ignore_errors,
        generate_api=not args.no_generate_api,
        generate_index=not args.no_generate_index,
    )

if __name__ == "__main__":
    main()