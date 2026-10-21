"""Partition correctness with tiny pages and isolated PostgreSQL records."""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from app.ingestion import ingest
from app.matching import advanced, complete_matching, naive_pairs, run_matching
from app.matching_pages import PAGE_SQL, persist_page, progress
from app.models import Audit, Criteria, Match, Outbox
from sqlalchemy import func, select, text

from backend.tests.test_integration import csv_bytes, product, register
from backend.tests.test_validation import valid_row


def setup_job(pg, monkeypatch, count=3):
    monkeypatch.setattr("app.matching_pages.PAGE_SIZE", 2)
    job = register(pg, monkeypatch, csv_bytes([valid_row(user_id=str(i)) for i in range(count)]))
    ingest(job.id)
    product(pg)
    product(pg, minimum_credit_score=None)
    return job


def payload(pg, job_id):
    state = progress(job_id)
    values = {
        "job_id": job_id,
        "demo": True,
        "after_user_id": state["after_user_id"],
        "after_product_id": state["after_product_id"],
        "page_size": state["page_size"],
    }
    rows = [dict(r) for r in pg.execute(text(PAGE_SQL), values).mappings()]
    evaluations = [
        {"user_id": r["user_id"], "product_id": r["product_id"], "status": advanced(r)[0]} for r in rows
    ]
    return evaluations, state["after_user_id"], state["after_product_id"]


def persist(pg, job_id, data):
    evaluations, user, product_id = data
    return persist_page(job_id, evaluations, "123", user, product_id)


def test_pages_equal_cartesian_oracle_and_notify_only_after_final_ack(pg, monkeypatch):
    job = setup_job(pg, monkeypatch)
    expected = naive_pairs(pg, job.id)
    state = progress(job.id)
    while state["more"]:
        state = persist(pg, job.id, payload(pg, job.id))
        assert not pg.scalar(select(Outbox.id).where(Outbox.workflow == "C"))
        if state["more"]:
            with pytest.raises(ValueError, match="persist successfully"):
                complete_matching(job.id, "123")
    assert state["page_count"] == 4  # Three full pages followed by the empty terminal page.
    actual = {(m.user_id, m.product_id, m.status) for m in pg.scalars(select(Match))}
    assert actual == expected and state["matches_created"] == len(expected)
    assert complete_matching(job.id, "123")["status"] == "COMPLETED"
    assert complete_matching(job.id, "124")["status"] == "COMPLETED"
    assert pg.scalar(select(func.count()).select_from(Outbox).where(Outbox.workflow == "C")) == 1
    assert not progress(job.id)["more"]


def test_page_replay_and_concurrent_duplicate_do_not_increment_counts(pg, monkeypatch):
    job = setup_job(pg, monkeypatch)
    data = payload(pg, job.id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        states = list(pool.map(lambda _: persist(pg, job.id, data), range(2)))
    assert all(state["page_count"] == 1 and state["matches_created"] == 2 for state in states)
    assert persist(pg, job.id, data)["page_count"] == 1
    assert pg.scalar(select(func.count()).select_from(Match)) == 2
    with pytest.raises(ValueError, match="paged"):
        run_matching(job.id)


def test_incorrect_or_future_page_rolls_back_without_releasing_c(pg, monkeypatch):
    job = setup_job(pg, monkeypatch)
    data, user, product_id = payload(pg, job.id)
    with pytest.raises(ValueError, match="disagrees"):
        persist_page(job.id, data[:-1], "123", user, product_id)
    with pytest.raises(ValueError, match="ahead"):
        persist_page(job.id, data, "123", 999999, 0)
    assert pg.scalar(select(func.count()).select_from(Match)) == 0
    assert not pg.scalar(select(Audit.id).where(Audit.workflow == "B"))
    assert not pg.scalar(select(Outbox.id).where(Outbox.workflow == "C"))


def test_criteria_drift_blocks_later_pages(pg, monkeypatch):
    job = setup_job(pg, monkeypatch)
    persist(pg, job.id, payload(pg, job.id))
    c = pg.scalar(select(Criteria).where(Criteria.minimum_credit_score.is_not(None)))
    c.minimum_credit_score = 701
    pg.commit()
    with pytest.raises(ValueError, match="criteria changed"):
        persist(pg, job.id, payload(pg, job.id))
    assert pg.scalar(select(Audit.status).where(Audit.workflow == "B")) == "PARTITIONING"
    assert not pg.scalar(select(Outbox.id).where(Outbox.workflow == "C"))


def test_empty_candidates_persist_then_ack_without_false_matches(pg, monkeypatch):
    job = setup_job(pg, monkeypatch, count=0)
    state = persist(pg, job.id, payload(pg, job.id))
    assert not state["more"] and state["matches_created"] == 0 and state["naive_candidates"] == 0
    complete_matching(job.id, "123")


def test_completed_legacy_job_is_replay_compatible(pg, monkeypatch):
    job = setup_job(pg, monkeypatch)
    run_matching(job.id)
    state = persist_page(job.id, [], "123", 0, 0)
    assert not state["more"]
    assert state["matches_created"] == 6


@pytest.mark.parametrize("count", [0, 1000, 1001])
def test_n8n_page_boundary(count):
    code = (
        "const $json={job_id:'test',candidates:Array.from({length:"
        + str(count)
        + "},(_,i)=>({user_id:i+1,product_id:1,minimum_monthly_income:null,minimum_credit_score:null,age_min:null,age_max:null,employment_requirements:null,criteria_complete:false}))};const run=()=>{"
        + Path("n8n/advanced_rules.js").read_text()
        + "};console.log(JSON.stringify(run()));"
    )
    result = subprocess.run(["node", "-"], input=code, capture_output=True, text=True)
    assert (result.returncode == 0) == (count <= 1000)


def test_n8n_code_handles_more_than_previous_total_cap_in_bounded_pages():
    code = (
        "let $json;const run=()=>{"
        + Path("n8n/advanced_rules.js").read_text()
        + "};let total=0;for(let offset=0;offset<51001;offset+=1000){$json={job_id:'test',after_user_id:offset,after_product_id:0,candidates:Array.from({length:Math.min(1000,51001-offset)},(_,i)=>({user_id:offset+i+1,product_id:1,minimum_monthly_income:null,minimum_credit_score:null,age_min:null,age_max:null,employment_requirements:null,criteria_complete:false}))};total+=run()[0].json.evaluations.length;}console.log(JSON.stringify({total}));"
    )
    result = subprocess.run(["node", "-"], input=code, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["total"] == 51001
