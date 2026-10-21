"""Deterministic exports for official n8n nodes; secrets remain credential references."""

import json
from pathlib import Path

from app.matching_pages import PAGE_SQL


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


def boolean_gate(name, expression, x):
    return node(
        name,
        "if",
        {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                "conditions": [
                    {
                        "id": name,
                        "leftValue": expression,
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        x,
        version=2.2,
    )


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
                + PAGE_SQL.replace(":job_id", "$1")
                .replace(":demo", "$2")
                .replace(":after_user_id", "$3")
                .replace(":after_product_id", "$4")
                .replace(":page_size", "$5")
                + ") SELECT $1::text AS job_id, $3::bigint AS after_user_id, $4::integer AS after_product_id, COALESCE(jsonb_agg(to_jsonb(candidates) ORDER BY user_id,product_id), '[]'::jsonb) AS candidates FROM candidates",
                "options": {
                    "queryReplacement": "={{[$json.job_id, $env.DEMO_MODE === 'true', $json.after_user_id, $json.after_product_id, $json.page_size]}}"
                },
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
            "=http://api:8000/internal/matching/{{$json.job_id}}/page",
            1380,
            body="={{JSON.stringify({...$json,execution_id:$execution.id})}}",
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
    fetch_progress = http(
        "Fetch matching progress", "=http://api:8000/internal/matching/{{$json.job_id}}/progress", 800, "GET"
    )
    page_required = boolean_gate("Matching page required", "={{$json.more}}", 900)
    more_pages = boolean_gate("More matching pages", "={{$json.more}}", 1750)
    b_links = chain([*b[:4], fetch_progress, page_required]) | chain(b[4:8]) | chain([b[7], more_pages])
    b_links[page_required["name"]] = {
        "main": [
            [{"node": b[4]["name"], "type": "main", "index": 0}],
            [{"node": b[8]["name"], "type": "main", "index": 0}],
        ]
    }
    b_links[more_pages["name"]] = {
        "main": [
            [{"node": fetch_progress["name"], "type": "main", "index": 0}],
            [{"node": b[8]["name"], "type": "main", "index": 0}],
        ]
    }
    workflow("B", "User loan matching", [*b, fetch_progress, page_required, more_pages], b_links)
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
    transport = http(
        "Select delivery transport",
        "=http://api:8000/internal/notifications/{{$json.job_id}}/transport",
        350,
        "GET",
    )
    transport_gate = boolean_gate("Explicit SES test gate", "={{$json.n8n_ses}}", 460)
    claim = http(
        "Reserve SES event",
        "=http://api:8000/internal/notifications/{{$json.job_id}}/claim",
        690,
        body="={{JSON.stringify({execution_id:$execution.id})}}",
    )
    claim["retryOnFail"] = False
    ready = boolean_gate("Reserved event ready", "={{$json.ready}}", 920)
    ses = node(
        "AWS SES controlled test",
        "awsSes",
        {
            "authentication": "iam",
            "resource": "email",
            "operation": "send",
            "fromEmail": "={{$json.from}}",
            "toAddresses": "={{[$json.to]}}",
            "subject": "={{$json.subject}}",
            "body": "={{$json.html}}",
            "isBodyHtml": True,
            "additionalFields": {},
        },
        1150,
    )
    ses.update(
        disabled=True,
        retryOnFail=False,
        onError="continueErrorOutput",
        credentials={"aws": {"id": "loan-ses-test", "name": "Loan SES controlled test"}},
    )
    receipt = node(
        "Build SES receipt",
        "code",
        {
            "jsCode": "const event=$('Reserve SES event').first().json;const id=$json.SendEmailResponse?.SendEmailResult?.MessageId ?? $json.MessageId;return [{json:{job_id:event.job_id,event_id:event.event_id,execution_id:$execution.id,status:typeof id==='string'&&id.length?'SENT':'UNKNOWN',provider_id:typeof id==='string'&&id.length?id:null}}];"
        },
        1380,
        version=2,
    )
    acknowledge = http(
        "Persist SES receipt",
        "=http://api:8000/internal/notifications/{{$json.job_id}}/receipt",
        1610,
        body="={{JSON.stringify($json)}}",
    )
    summary = http(
        "Summarize reserved delivery",
        "=http://api:8000/internal/notifications/{{$json.job_id}}/summary",
        1150,
        body="={{JSON.stringify({execution_id:$execution.id})}}",
    )
    links = (
        chain([c[0], c[1], transport, transport_gate])
        | chain([claim, ready])
        | chain([ses, receipt, acknowledge, c[3]])
        | chain([summary, c[3]])
        | chain([c[2], c[3]])
    )
    links[transport_gate["name"]] = {
        "main": [
            [{"node": claim["name"], "type": "main", "index": 0}],
            [{"node": c[2]["name"], "type": "main", "index": 0}],
        ]
    }
    links[ready["name"]] = {
        "main": [
            [{"node": ses["name"], "type": "main", "index": 0}],
            [{"node": summary["name"], "type": "main", "index": 0}],
        ]
    }
    links[ses["name"]]["main"].append([{"node": receipt["name"], "type": "main", "index": 0}])
    workflow(
        "C",
        "User notification",
        [*c, transport, transport_gate, claim, ready, ses, receipt, acknowledge, summary],
        links,
    )
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
