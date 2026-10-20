"""Deterministic exports for official n8n nodes; secrets remain credential references."""

import json
from pathlib import Path

from app.matching import CANDIDATE_SQL


def node(name, kind, params, x, y=0, version=1):
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "type": "n8n-nodes-base." + kind,
        "typeVersion": version,
        "position": [x, y],
        "parameters": params,
    }


def http(name, path, x, method="POST", body=None):
    params = {
        "url": path,
        "method": method,
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "options": {"timeout": 120000},
    }
    if body is not None:
        params.update(sendBody=True, specifyBody="json", jsonBody=body)
    result = node(name, "httpRequest", params, x, version=4.2)
    result.update(
        credentials={"httpHeaderAuth": {"id": "loan-internal-header", "name": "Loan internal header"}},
        retryOnFail=True,
        maxTries=3,
        waitBetweenTries=2000,
    )
    return result


def webhook(letter):
    result = node(
        "Authenticated webhook",
        "webhook",
        {
            "httpMethod": "POST",
            "path": f"loan-{letter.lower()}",
            "authentication": "headerAuth",
            "responseMode": "onReceived",
            "options": {},
        },
        0,
        version=2,
    )
    result["webhookId"] = f"loan-{letter.lower()}-webhook"
    result["credentials"] = {"httpHeaderAuth": {"id": "loan-internal-header", "name": "Loan internal header"}}
    return result


def workflow(letter, name, nodes, connections):
    value = {
        "id": f"loan-workflow-{letter.lower()}",
        "name": f"{letter} · {name}",
        "active": False,
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "timezone": "Asia/Kolkata",
            "saveDataSuccessExecution": "all",
            "saveDataErrorExecution": "all",
        },
        "pinData": {},
        "tags": [],
    }
    Path(f"n8n/workflows/{letter}_{name.lower().replace(' ', '_')}.json").write_text(
        json.dumps(value, indent=2), encoding="utf-8"
    )


def chain(nodes):
    return {
        a["name"]: {"main": [[{"node": b["name"], "type": "main", "index": 0}]]}
        for a, b in zip(nodes, nodes[1:], strict=False)
    }


def main():
    check = "const id=$json.body?.job_id;if(typeof id!=='string'||!/^[-0-9a-f]{36}$/.test(id))throw new Error('Invalid job ID');return [{json:{job_id:id}}];"
    b = [
        webhook("B"),
        node("Validate job ID", "code", {"jsCode": check}, 230, version=2),
        http("Fetch completed job", "=http://api:8000/internal/jobs/{{$json.job_id}}", 460, "GET"),
        node(
            "Require completed ingestion",
            "code",
            {
                "jsCode": "if($json.status!=='COMPLETED')throw new Error('Ingestion not complete');return [{json:{job_id:$json.id}}];"
            },
            690,
            version=2,
        ),
        node(
            "SQL structured candidate prefilter",
            "postgres",
            {
                "operation": "executeQuery",
                "query": "WITH candidates AS ("
                + CANDIDATE_SQL.replace(":job_id", "$1").replace(":demo", "$2")
                + " LIMIT 50001) SELECT $1::text AS job_id, COALESCE(jsonb_agg(to_jsonb(candidates)), '[]'::jsonb) AS candidates FROM candidates",
                "options": {"queryReplacement": "={{[$json.job_id, $env.DEMO_MODE === 'true']}}"},
            },
            920,
            version=2.6,
        ),
        node(
            "Advanced deterministic rules",
            "code",
            {"jsCode": Path("n8n/advanced_rules.js").read_text()},
            1150,
            version=2,
        ),
        http(
            "Validate and bulk persist",
            "=http://api:8000/internal/matching/{{$json.job_id}}",
            1380,
            body="={{JSON.stringify({evaluations:$json.evaluations,execution_id:$execution.id})}}",
        ),
        node(
            "Validate measured metrics",
            "code",
            {
                "jsCode": "if($json.sql_candidates>$json.naive_candidates)throw new Error('Invalid metrics');if($json.llm_evaluations!==0)throw new Error('LLM disabled');return $input.all();"
            },
            1610,
            version=2,
        ),
    ]
    b.append(
        http(
            "Acknowledge B and queue C",
            "=http://api:8000/internal/matching/{{$json.job_id}}/complete",
            1840,
            body="={{JSON.stringify({execution_id:$execution.id})}}",
        )
    )
    b[4]["credentials"] = {"postgres": {"id": "loan-domain-postgres", "name": "Loan domain PostgreSQL"}}
    workflow("B", "User loan matching", b, chain(b))
    c = [
        webhook("C"),
        node("Validate job ID", "code", {"jsCode": check}, 230, version=2),
        http(
            "Grouped allowlisted delivery",
            "=http://api:8000/internal/notifications/{{$json.job_id}}",
            460,
            body="={{JSON.stringify({execution_id:$execution.id})}}",
        ),
        node(
            "Delivery metrics",
            "code",
            {
                "jsCode": "if($json.sent<0||$json.pending<0)throw new Error('Invalid delivery metrics');return $input.all();"
            },
            690,
            version=2,
        ),
    ]
    workflow("C", "User notification", c, chain(c))
    schedule = node(
        "Daily schedule", "scheduleTrigger", {"rule": {"interval": [{"triggerAtHour": 9}]}}, 0, version=1.2
    )
    source = node(
        "Approved source configuration",
        "code",
        {
            "jsCode": "const sources="
            + Path("n8n/sources.json").read_text()
            + ";return sources.map(s=>({json:s}));"
        },
        230,
        version=2,
    )
    gate = node(
        "Permission review gate",
        "if",
        {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                "conditions": [
                    {
                        "id": "approved",
                        "leftValue": "={{$json.approved}}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        460,
        version=2.2,
    )
    fetch = node(
        "Fetch official product page",
        "httpRequest",
        {
            "url": "={{$json.url}}",
            "options": {
                "timeout": 15000,
                "redirect": {"redirect": {"followRedirects": False}},
                "response": {"response": {"responseFormat": "text", "outputPropertyName": "data"}},
            },
        },
        690,
        -150,
        version=4.2,
    )
    fetch.update(retryOnFail=True, maxTries=3, waitBetweenTries=5000, onError="continueErrorOutput")
    failed = http(
        "Audit failed fetch",
        "http://api:8000/internal/discovery/audit",
        920,
        body="={{JSON.stringify({url:$('Permission review gate').item.json.url,status:'FAILED',detail:String($json.error?.message || $json.message || 'Source fetch failed').slice(0,1000)})}}",
    )
    failed["position"][1] = -300
    normalize = node(
        "Bound and normalize response",
        "code",
        {
            "mode": "runOnceForEachItem",
            "jsCode": "const html=$json.data;if(typeof html!=='string'||html.length>2000000)throw new Error('Invalid HTML response');return {json:{html,source_id:$('Permission review gate').item.json.id}};",
        },
        920,
        -150,
        version=2,
    )
    persist = http(
        "Extract validate deduplicate upsert",
        "http://api:8000/internal/discovery/extract",
        1150,
        body="={{JSON.stringify({...$json,execution_id:$execution.id})}}",
    )
    blocked = http(
        "Audit blocked source",
        "http://api:8000/internal/discovery/audit",
        690,
        body="={{JSON.stringify({url:$json.url,detail:$json.review_notes})}}",
    )
    manual = node("Manual fixture demo", "manualTrigger", {}, 0, 300)
    fixture_hook = webhook("A-demo")
    fixture_hook["name"] = "Authenticated fixture discovery"
    fixture_hook["id"] = "fixture-discovery-hook"
    fixture_hook["position"] = [0, 500]
    fixtures = node(
        "Fixture source configuration",
        "code",
        {"jsCode": "return ['incomplete','independent','salaried'].map(fixture_id=>({json:{fixture_id}}));"},
        230,
        300,
        version=2,
    )
    fetch_fixture = http(
        "Fetch fictional source HTML",
        "=http://api:8000/internal/discovery/fixture-html/{{$json.fixture_id}}",
        460,
        "GET",
    )
    fetch_fixture["position"][1] = 300
    fetch_fixture["parameters"]["options"]["response"] = {
        "response": {"responseFormat": "text", "outputPropertyName": "data"}
    }
    normalize_fixture = node(
        "Normalize fixture HTML",
        "code",
        {
            "mode": "runOnceForEachItem",
            "jsCode": "if(typeof $json.data!=='string'||$json.data.length>2000000)throw new Error('Invalid fixture HTML');return {json:{html:$json.data,fixture_id:$('Fixture source configuration').item.json.fixture_id}};",
        },
        690,
        300,
        version=2,
    )
    persist_fixture = http(
        "Extract validate and upsert fictional products",
        "http://api:8000/internal/discovery/extract",
        920,
        body="={{JSON.stringify({...$json,execution_id:$execution.id})}}",
    )
    persist_fixture["position"][1] = 300
    nodes = [
        schedule,
        source,
        gate,
        fetch,
        normalize,
        persist,
        blocked,
        failed,
        manual,
        fixture_hook,
        fixtures,
        fetch_fixture,
        normalize_fixture,
        persist_fixture,
    ]
    connections = (
        chain([schedule, source, gate])
        | chain([fetch, normalize, persist])
        | chain([manual, fixtures, fetch_fixture, normalize_fixture, persist_fixture])
        | chain([fixture_hook, fixtures])
    )
    connections[gate["name"]] = {
        "main": [
            [{"node": fetch["name"], "type": "main", "index": 0}],
            [{"node": blocked["name"], "type": "main", "index": 0}],
        ]
    }
    connections[fetch["name"]]["main"].append([{"node": failed["name"], "type": "main", "index": 0}])
    workflow("A", "Loan product discovery", nodes, connections)


if __name__ == "__main__":
    main()
