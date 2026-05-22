import json
import argparse
import sys
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description="Convert pip-audit JSON to HTML")
    parser.add_argument("input", help="Path to pip-audit JSON file")
    parser.add_argument("output", help="Path to save HTML report")
    args = parser.parse_args()

    try:
        with open(args.input, 'r') as f:
            # pip-audit json output is a list of results or a dict depending on version
            data = json.load(f)
    except Exception as e:
        print(f"Error reading audit JSON: {e}")
        sys.exit(1)

    html_template = """
    <html>
    <head>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; line-height: 1.6; color: #24292e; max-width: 1000px; margin: 40px auto; padding: 0 20px; }
            h1 { border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
            .summary { background: #f6f8fa; padding: 15px; border-radius: 6px; margin-bottom: 20px; border: 1px solid #d1d5da; }
            .vuln { border: 1px solid #e1e4e8; border-radius: 6px; margin-bottom: 16px; padding: 16px; }
            .vuln-header { font-weight: bold; font-size: 1.1em; color: #d73a49; }
            .no-vulns { color: #28a745; font-weight: bold; font-size: 1.2em; text-align: center; margin-top: 50px; }
            .tag { display: inline-block; padding: 2px 8px; font-size: 0.8em; border-radius: 20px; background: #f1f1f1; margin-right: 5px; }
        </style>
        <title>Dependency Audit Report</title>
    </head>
    <body>
        <h1>Dependency Security Audit</h1>
        <div class="summary">Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</div>
    """

    found_vulns = []
    # Normalize pip-audit's varied JSON structures
    dependencies = data if isinstance(data, list) else data.get("dependencies", [])
    
    for dep in dependencies:
        vulns = dep.get("vulns", [])
        for v in vulns:
            found_vulns.append({"name": dep["name"], "version": dep["version"], "vuln": v})

    if not found_vulns:
        html_template += '<div class="no-vulns">✅ No known vulnerabilities found in dependencies.</div>'
    else:
        for item in found_vulns:
            v = item["vuln"]
            html_template += f"""
            <div class="vuln">
                <div class="vuln-header">{item['name']} (v{item['version']})</div>
                <div><span class="tag">ID: {v['id']}</span> <span class="tag">Fix: {', '.join(v.get('fix_versions', ['N/A']))}</span></div>
                <p>{v.get('description', 'No description provided.')}</p>
            </div>
            """

    html_template += "</body></html>"

    with open(args.output, 'w') as f:
        f.write(html_template)
    print(f"HTML report generated: {args.output}")

if __name__ == "__main__":
    main()