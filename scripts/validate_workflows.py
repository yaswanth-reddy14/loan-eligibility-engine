import json
from pathlib import Path


def validate(path: Path) -> None:
    workflow = json.loads(path.read_text(encoding="utf-8"))
    names = {node["name"] for node in workflow["nodes"]}
    assert len(names) == len(workflow["nodes"])
    allowed = {"webhook", "httpRequest", "code", "scheduleTrigger", "manualTrigger", "if", "postgres", "awsSes"}
    for node in workflow["nodes"]:
        assert node["type"].removeprefix("n8n-nodes-base.") in allowed
        if node["type"].endswith("webhook"):
            assert node["parameters"]["authentication"] == "headerAuth"
        if node["type"].endswith("awsSes"):
            assert node.get("disabled") is True, "SES export must require deliberate operator enablement"
            assert node.get("retryOnFail") is False
            assert node["parameters"]["additionalFields"] == {}, "No extra recipient paths"
    for source, edges in workflow["connections"].items():
        assert source in names
        for outputs in edges["main"]:
            for output in outputs:
                assert output["node"] in names
    assert "REPLACE_WITH" not in path.read_text()


def main() -> None:
    paths = list(Path("n8n/workflows").glob("*.json"))
    assert len(paths) == 3
    for path in paths:
        validate(path)
    print("3 connected workflow exports passed structural validation; runtime import is a separate check.")


if __name__ == "__main__":
    main()
