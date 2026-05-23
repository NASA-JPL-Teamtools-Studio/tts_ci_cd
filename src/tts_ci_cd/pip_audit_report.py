import json
import argparse
import sys
from datetime import datetime
from tts_data_utils.core.generic import GenericContainer
from tts_html_utils.core.components import Link, Div, H1, Paragraph
from tts_html_utils.core.compiler import HtmlCompiler

def main():
    parser = argparse.ArgumentParser(description="Convert pip-audit JSON to HTML")
    parser.add_argument("input", help="Path to pip-audit JSON file")
    parser.add_argument("output", help="Path to save HTML report")
    args = parser.parse_args()

    try:
        with open(args.input, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading audit JSON: {e}")
        sys.exit(1)

    compiler = HtmlCompiler(title="Dependency Audit Report")

    compiler.add_body_component(H1("Dependency Security Audit"))
    
    summary_div = Div(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        style={
            'background': '#f6f8fa',
            'padding': '15px',
            'border-radius': '6px',
            'margin-bottom': '20px',
            'border': '1px solid #d1d5da'
        }
    )
    compiler.add_body_component(summary_div)

    found_vulns = []
    dependencies = data if isinstance(data, list) else data.get("dependencies", [])
    
    for dep in dependencies:
        vulns = dep.get("vulns", [])
        for v in vulns:
            v_id = v['id']
            
            if v_id.startswith("GHSA"):
                url = f"https://github.com/advisories/{v_id}"
            elif v_id.startswith("PYSEC"):
                url = f"https://osv.dev/vulnerability/{v_id}"
            else:
                url = f"https://osv.dev/vulnerability/{v_id}"

            found_vulns.append({
                "Library": dep["name"], 
                "Version": dep["version"], 
                "Vulnerability URL": Link(text=v_id, href=url),
                "ID": v_id,
                "Fix Versions": '<br />'.join(v['fix_versions'])
            })

    if not found_vulns:
        no_vulns_div = Div(
            "✅ No known vulnerabilities found in dependencies.",
            style={
                'color': '#28a745',
                'font-weight': 'bold',
                'font-size': '1.2em',
                'text-align': 'center',
                'margin-top': '50px'
            }
        )
        compiler.add_body_component(no_vulns_div)
    else:
        table = GenericContainer(raw_data=found_vulns).power_table(add_filters='local', add_sorting='local')
        compiler.add_body_component(table)

    compiler.render_to_file(args.output)
    print(f"HTML report generated: {args.output}")

if __name__ == "__main__":
    main()