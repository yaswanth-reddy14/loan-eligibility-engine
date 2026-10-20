import argparse
import json
import statistics
import time
from pathlib import Path

from app.config import settings
from app.db import engine
from app.matching import CANDIDATE_SQL, advanced, naive_pairs
from app.models import Job
from sqlalchemy import select, text
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id")
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("iterations must be positive")
    with Session(engine()) as db:
        job_id = args.job_id or db.scalar(
            select(Job.id)
            .where(Job.status == "COMPLETED", Job.accepted == 10000)
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        if not job_id:
            raise SystemExit("Ingest supplied 10,000-row users.csv first, or pass --job-id explicitly")
        samples = []
        for iteration in range(args.iterations + 1):
            start = time.perf_counter()
            naive = naive_pairs(db, job_id)
            naive_seconds = time.perf_counter() - start
            start = time.perf_counter()
            result = (
                db.execute(text(CANDIDATE_SQL), {"job_id": job_id, "demo": settings().demo_mode})
                .mappings()
                .all()
            )
            sql_seconds = time.perf_counter() - start
            optimized = {(row["user_id"], row["product_id"], advanced(dict(row))[0]) for row in result}
            optimized_seconds = time.perf_counter() - start
            assert naive == optimized, "Naive and SQL pipeline outcomes differ"
            if iteration:
                samples.append(
                    {
                        "naive_seconds": naive_seconds,
                        "optimized_seconds": optimized_seconds,
                        "sql_execution_and_fetch_seconds": sql_seconds,
                    }
                )
        plan = db.execute(
            text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + CANDIDATE_SQL),
            {"job_id": job_id, "demo": settings().demo_mode},
        ).scalar_one()
        report = {
            "job_id": job_id,
            "equivalent": True,
            "pairs": len(optimized),
            "naive_seconds": statistics.median(s["naive_seconds"] for s in samples),
            "sql_execution_and_fetch_seconds": statistics.median(
                s["sql_execution_and_fetch_seconds"] for s in samples
            ),
            "optimized_seconds": statistics.median(s["optimized_seconds"] for s in samples),
            "explain_execution_ms": plan[0]["Execution Time"],
            "explain": plan,
            "iterations": args.iterations,
            "samples": samples,
            "note": "One warmup, five default measured runs; median local Python comparison excludes n8n, persistence and delivery. Production revalidates candidates in a second SQL pass. Not a load test or whole-pipeline speedup.",
        }
        Path("reports").mkdir(exist_ok=True)
        Path("reports/benchmark.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({key: value for key, value in report.items() if key != "explain"}, indent=2))


if __name__ == "__main__":
    main()
