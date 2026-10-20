import json
from pathlib import Path

import httpx
from app.config import settings


def main() -> None:
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
        checks = {}
        for name, path, headers, expected in [
            ("health", "/health", {}, 200),
            ("dashboard_html", "/", {}, 200),
            ("javascript", "/assets/app.js", {}, 200),
            ("css", "/assets/style.css", {}, 200),
            ("unauthenticated_api", "/api/dashboard", {}, 401),
            ("authenticated_api", "/api/dashboard", {"Authorization": "Bearer " + settings().api_token}, 200),
        ]:
            response = client.get(path, headers=headers)
            assert response.status_code == expected, (name, response.status_code)
            checks[name] = response.status_code
        assert "Loan Eligibility Engine" in client.get("/").text
        Path("reports/api-smoke.json").write_text(json.dumps(checks, indent=2))
        print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
