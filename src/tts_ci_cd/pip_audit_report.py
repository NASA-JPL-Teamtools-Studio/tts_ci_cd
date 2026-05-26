import json
import argparse
import sys
import requests
from datetime import datetime
from tts_data_utils.core.generic import GenericContainer
from tts_html_utils.core.components import Link, Div, H1, Paragraph
from tts_html_utils.core.compiler import HtmlCompiler
from tts_ci_cd.tts_ci_cd_data_utils.pip_audit import PipAuditContainer
from cvss import CVSS3
import yaml

# Cache API lookups to speed up runs and avoid rate limits
SEVERITY_CACHE = {}

def extract_label_from_record(data):
    """Helper to extract and normalize a severity label from a single OSV record."""
    # 1. Try to get the human-readable label (Common for GHSA)
    db_specific = data.get("database_specific", {})
    if "severity" in db_specific and isinstance(db_specific["severity"], str):
        label = db_specific["severity"].upper()
        return "MODERATE" if label == "MEDIUM" else label

    # 2. Try to calculate it from a CVSS V3 Vector
    for sev in data.get("severity", []):
        if sev.get("type") == "CVSS_V3":
            vector = sev.get("score")
            try:
                c = CVSS3(vector)
                score = c.base_score
                if score >= 9.0: return "CRITICAL"
                if score >= 7.0: return "HIGH"
                if score >= 4.0: return "MODERATE"
                if score > 0.0:  return "LOW"
            except Exception as e:
                print(f"Warning: Failed to parse CVSS vector '{vector}': {e}")
                pass
                
    return None

def get_severity_label(vuln_id):
    """Robust lookup that pivots to aliases AND related IDs if the primary record is empty."""
    if vuln_id in SEVERITY_CACHE:
        return SEVERITY_CACHE[vuln_id]

    label = "UNKNOWN"
    base_url = "https://api.osv.dev/v1/vulns/"

    try:
        # Step 1: Query the primary ID
        resp = requests.get(f"{base_url}{vuln_id}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            
            # Extract from the primary record
            extracted = extract_label_from_record(data)
            if extracted:
                SEVERITY_CACHE[vuln_id] = extracted
                return extracted

            # Step 2: Alias & Related Pivot
            # Python wrappers of vulnerable C-libraries (like libwebp) use "related" instead of "aliases"
            pivot_ids = data.get("aliases", []) + data.get("related", [])
            
            # Prioritize GitHub Security Advisories, then standard CVEs
            best_pivots = [a for a in pivot_ids if a.startswith("GHSA")] + \
                          [a for a in pivot_ids if a.startswith("CVE")]

            for pivot_id in best_pivots:
                pivot_resp = requests.get(f"{base_url}{pivot_id}", timeout=5)
                if pivot_resp.status_code == 200:
                    pivot_data = pivot_resp.json()
                    extracted = extract_label_from_record(pivot_data)
                    if extracted:
                        SEVERITY_CACHE[vuln_id] = extracted
                        return extracted

    except Exception as e:
        print(f"Error fetching severity for {vuln_id}: {e}")

    # Step 3: Fallback
    SEVERITY_CACHE[vuln_id] = label
    return label

def main():
    parser = argparse.ArgumentParser(description="Convert pip-audit JSON to HTML")
    parser.add_argument("input", help="Path to pip-audit JSON file")
    parser.add_argument("output", help="Path to save HTML report")
    parser.add_argument("summary", help="Path to save summary text file")
    args = parser.parse_args()

    try:
        with open(args.input, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading audit JSON: {e}")
        sys.exit(1)

    found_vulns = []
    dependencies = data if isinstance(data, list) else data.get("dependencies", [])
    
    for dep in dependencies:
        vulns = dep.get("vulns", [])
        for v in vulns:
            v_id = v['id']
            
            if v_id.startswith("GHSA"):
                url = f"https://github.com/advisories/{v_id}"
            else:
                url = f"https://osv.dev/vulnerability/{v_id}"

            severity = get_severity_label(v_id)
            
            found_vulns.append({
                "Library": dep["name"], 
                "Version": dep["version"], 
                "Vulnerability URL": Link(text=v_id, href=url),
                "ID": v_id,
                "Fix Versions": '<br />'.join(v.get('fix_versions', [])),
                "Severity": severity
            })

    severity_counts = {
        'LOW': 0,
        'MODERATE': 0,
        'HIGH': 0,
        'CRITICAL': 0,
        'UNKNOWN': 0
    }
    
    for vuln in found_vulns:
        severity = vuln['Severity']
        if severity in severity_counts:
            severity_counts[severity] += 1
        else:
            severity_counts['UNKNOWN'] += 1
    
    if severity_counts['CRITICAL'] > 0:
        gumball = 'BLACKRED'
    elif severity_counts['HIGH'] > 0:
        gumball = 'RED'
    elif severity_counts['MODERATE'] > 0:
        gumball = 'ORANGE'
    elif severity_counts['LOW'] > 0:
        gumball = 'YELLOW'
    else:
        gumball = 'GREEN'

    summary_data = {
        'gumball': gumball,
        'severity_counts': {
            'low': severity_counts['LOW'],
            'moderate': severity_counts['MODERATE'],
            'high': severity_counts['HIGH'],
            'critical': severity_counts['CRITICAL'],
            'unknown': severity_counts['UNKNOWN']
        },
        'total_vulnerabilities': len(found_vulns),
        'generated_at': datetime.now().isoformat()
    }
    
    with open(args.summary, 'w') as f:
        yaml.dump(summary_data, f, default_flow_style=False)
    
    summary_text = f"Low: {severity_counts['LOW']}, Moderate: {severity_counts['MODERATE']}, High: {severity_counts['HIGH']}, Critical: {severity_counts['CRITICAL']}, Unknown: {severity_counts['UNKNOWN']}"
    print(f"Summary generated: {summary_text}")

    compiler = HtmlCompiler(title="Dependency Audit Report")

    compiler.add_body_component(H1("Dependency Security Audit"))
    
    summary_div = Div(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {summary_text}",
        style={
            'background': '#f6f8fa',
            'padding': '15px',
            'border-radius': '6px',
            'margin-bottom': '20px',
            'border': '1px solid #d1d5da',
            'font-weight': 'bold'
        }
    )
    compiler.add_body_component(summary_div)

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
        # Changed .sort('Criticality') to .sort('Severity') to match the dict keys
        table = PipAuditContainer(raw_data=found_vulns).sort('Severity').sort_by_severity().power_table(add_filters='local', add_sorting='local')
        compiler.add_body_component(table)

    compiler.render_to_file(args.output)
    print(f"HTML report generated: {args.output}")

if __name__ == "__main__":
    main()