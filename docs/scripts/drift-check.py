#!/usr/bin/env python3
"""NewsIQ API Documentation Drift Checking Tool.

Scans FastAPI routers in apps/api/app/api/v1/ and matches registered routes against
markdown documentation files under docs/api/ to detect undocumented or outdated endpoints.
"""

import os
import re
import sys
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
API_SRC_DIR = BASE_DIR / "apps" / "api" / "app" / "api" / "v1"
DOCS_API_DIR = BASE_DIR / "docs" / "api"

# Mapping from FastAPI source files to markdown documentation files
ROUTER_MAPPING = {
    "auth.py": "auth.md",
    "oauth.py": "auth.md",
    "consent.py": "consent.md",
    "users.py": "users.md",
    "sources.py": "sources.md",
    "stories.py": "stories.md",
}

# Prefix mapping for validation reporting
PREFIX_MAPPING = {
    "auth.py": "/api/v1/auth",
    "oauth.py": "/api/v1/auth",
    "consent.py": "/api/v1/consent",
    "users.py": "/api/v1/users",
    "sources.py": "/api/v1/sources",
    "stories.py": "/api/v1/stories",
}


def extract_routes_from_code(file_path: Path) -> list[tuple[str, str]]:
    """Parse a python file to extract registered FastAPI endpoints.

    Returns:
        List of tuples: (HTTP_METHOD, ROUTE_PATH)
    """
    routes = []
    if not file_path.exists():
        return routes

    # Matches decorators like @router.get("/profile") or @router.post("/login", response_model=...)
    route_decorator_pattern = re.compile(
        r"@router\.(get|post|put|patch|delete)\s*\(\s*[\"']([^\"']+)[\"']"
    )

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        for match in route_decorator_pattern.finditer(content):
            method = match.group(1).upper()
            path = match.group(2)
            routes.append((method, path))

    return routes


def check_route_in_docs(doc_path: Path, method: str, path: str, route_prefix: str) -> bool:
    """Check if an endpoint (HTTP Method + Route Path) is referenced in the markdown file."""
    if not doc_path.exists():
        return False

    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Normalize patterns:
    # 1. Matches "POST /register" or "POST /api/v1/auth/register"
    # 2. Matches "POST `/register`" or "POST `/api/v1/auth/register`"
    # 3. Matches `POST /register` in tables or headings
    
    # Trim trailing slashes from path checks for flexibility
    trimmed_path = path.rstrip("/")
    escaped_path = re.escape(trimmed_path)
    escaped_prefix_path = re.escape((route_prefix + trimmed_path).replace("//", "/"))

    patterns = [
        # Match with or without backticks, e.g. "POST /register" or "POST `/register`"
        rf"{method}\s+`?{escaped_path}`?",
        rf"{method}\s+`?{escaped_prefix_path}`?",
        # Match inside tables or bullet points, e.g., "**POST** | `/register`"
        rf"{method}.*?`?{escaped_path}`?",
        rf"{method}.*?`?{escaped_prefix_path}`?",
    ]

    for pattern in patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True

    return False


def main():
    print("[INFO] Starting NewsIQ API Documentation Drift Audit...")
    
    total_endpoints = 0
    drift_detected = False
    report_lines = [
        "# NewsIQ API Documentation Drift Report",
        "",
        "This report is generated automatically by `docs/scripts/drift-check.py` to identify",
        "missing or outdated references in `/docs/api/` compared to registered FastAPI endpoints.",
        "",
        "| Source Router | Endpoint | Expected Doc File | Status |",
        "| :--- | :--- | :--- | :---: |"
    ]

    missing_docs_count = 0
    covered_docs_count = 0

    for source_file, doc_file in ROUTER_MAPPING.items():
        src_path = API_SRC_DIR / source_file
        doc_path = DOCS_API_DIR / doc_file
        prefix = PREFIX_MAPPING.get(source_file, "")

        if not src_path.exists():
            print(f"[WARN] Source file not found: {src_path.relative_to(BASE_DIR)}")
            continue

        routes = extract_routes_from_code(src_path)
        for method, path in routes:
            total_endpoints += 1
            is_documented = check_route_in_docs(doc_path, method, path, prefix)
            full_route_str = f"{method} {prefix}{path}".replace("//", "/")

            if is_documented:
                status_icon = "✅ Documented"
                covered_docs_count += 1
            else:
                status_icon = "❌ MISSING"
                missing_docs_count += 1
                drift_detected = True
                print(f"[DRIFT] {full_route_str} is not documented in {doc_file}")

            report_lines.append(
                f"| `{source_file}` | `{full_route_str}` | `docs/api/{doc_file}` | {status_icon} |"
            )

    # Compile Summary
    summary_section = [
        "",
        "## Audit Summary",
        "",
        f"- **Audit Execution Time**: {os.popen('date /t').read().strip() if os.name == 'nt' else os.popen('date').read().strip()}",
        f"- **Total Registered Endpoints**: {total_endpoints}",
        f"- **Documented Coverage**: {covered_docs_count} ({100*covered_docs_count/total_endpoints:.1f}% if {total_endpoints} > 0 else 0)",
        f"- **Undocumented Endpoints**: {missing_docs_count}",
        "",
        "---",
        ""
    ]
    
    # Insert summary near the top
    report_lines = report_lines[:2] + summary_section + report_lines[2:]

    # Write report file
    report_path = BASE_DIR / "docs" / "drift-report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")
    
    print(f"\n[OK] Written drift audit report to: {report_path.relative_to(BASE_DIR)}")

    if drift_detected:
        print("\n[FAIL] Audit Failed: API documentation drift detected! Please update /docs/api/ references.")
        sys.exit(1)
    else:
        print("\n[SUCCESS] Audit Succeeded: All endpoints are successfully documented!")
        sys.exit(0)


if __name__ == "__main__":
    main()
