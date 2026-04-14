import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

import config
from analyzer import JobAnalyzer


def _send_to_nextjs_api(path: str, payload: object):
    api_base = config.NEXTJS_API_URL
    if not api_base:
        print("[WORKER] NEXTJS_API_URL not configured; skipping Next.js API request")
        return None

    url = api_base.rstrip("/") + path
    body = json.dumps(payload, default=str).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)
    except urllib.error.HTTPError as error:
        payload_text = error.read().decode("utf-8")
        print(f"[WORKER] Next.js API HTTP error at {url}: {error.code} {payload_text}")
    except urllib.error.URLError as error:
        print(f"[WORKER] Could not connect to Next.js API at {url}: {error}")
    except Exception as error:
        print(f"[WORKER] Error posting to Next.js API: {error}")
    return None


def _claim_queue_jobs(batch_size: int, worker_id: str) -> list[dict]:
    result = _send_to_nextjs_api(
        "/api/jobs/claim",
        {"maxItems": batch_size, "workerId": worker_id},
    )
    if not result or not result.get("success"):
        return []
    return result.get("items", [])


def _complete_queue_job(queue_id: str, analyzed_job: dict) -> None:
    result = _send_to_nextjs_api(
        "/api/jobs/complete",
        {"queueId": queue_id, "analyzedJob": analyzed_job},
    )
    if not result:
        print(f"[WORKER] Failed to complete queue item {queue_id}")
    elif not result.get("success"):
        print(f"[WORKER] Queue completion error for {queue_id}:", result.get("error", "unknown"))


def _job_relevance(job: dict) -> int:
    try:
        return int(job.get("job_relevance_0_100") or 0)
    except (TypeError, ValueError):
        return 0


def _process_queue_item(analyzer: JobAnalyzer, queue_item: dict, min_rel: int) -> None:
    try:
        payload = queue_item.get("payload") or {}
        # Handle case where payload is a JSON string instead of dict
        if isinstance(payload, str):
            payload = json.loads(payload)
        raw_post = payload if isinstance(payload, dict) else {}
    except (json.JSONDecodeError, TypeError):
        raw_post = {}

    try:
        analyzed = analyzer.analyze_all([raw_post])
        result = analyzed[0]
        _complete_queue_job(queue_item["id"], result)

        if result.get("is_fit") and _job_relevance(result) >= min_rel:
            print(
                "[WORKER] Fit job ready:",
                result.get("role_detected", "Unknown role"),
                "@",
                result.get("company_detected", "Unknown company"),
                f"score={result.get('fit_score', 0)}",
            )
    except Exception as e:
        print(f"[WORKER] Error analyzing queue item {queue_item['id']}: {e}")


def _process_queue_loop(analyzer: JobAnalyzer, min_rel: int, batch_size: int = 1) -> None:
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    print(f"[WORKER] Starting queue processor {worker_id} (batch size: {batch_size})")

    while True:
        queue_items = _claim_queue_jobs(batch_size, worker_id)
        if not queue_items:
            print("[WORKER] Queue empty; sleeping 10 seconds")
            time.sleep(10)
            continue

        for item in queue_items:
            print(f"[WORKER] Processing queue item {item['id']}")
            _process_queue_item(analyzer, item, min_rel)
            time.sleep(0.5)  # Small delay between items


def main():
    parser = argparse.ArgumentParser(description="LinkedIn job queue worker")
    parser.add_argument(
        "--min-job-relevance",
        type=int,
        default=0,
        metavar="N",
        help="Only show matching jobs with job_relevance_0_100 >= N (0–100). Default: 0.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        metavar="N",
        help="Number of jobs to claim and process at once. Default: 1.",
    )
    parser.add_argument(
        "--ai-timeout",
        type=int,
        default=None,
        metavar="SECONDS",
        help="Override AI request timeout in seconds. If not set, uses config value.",
    )
    args = parser.parse_args()

    min_rel = max(0, min(100, args.min_job_relevance))
    batch_size = max(1, args.batch_size)

    print("\n" + "#" * 60)
    print("#  LINKEDIN JOB QUEUE WORKER")
    print("#" * 60)

    print("\n[WORKER] Loading configuration...")
    print(f"  OpenAI Model: {config.OPENAI_MODEL}")
    print(f"  OpenAI Base URL: {config.OPENAI_BASE_URL}")
    ai_timeout = args.ai_timeout if args.ai_timeout is not None else config.AI_REQUEST_TIMEOUT
    print(f"  AI request timeout (s): {ai_timeout}")
    print(f"  Min job relevance (display filter): {min_rel}")
    print(f"  Batch size: {batch_size}")

    if not config.NEXTJS_API_URL:
        print("[WORKER] NEXTJS_API_URL not configured. Cannot run worker.")
        sys.exit(1)

    print("\n[WORKER] Loading profile data from myData/...")
    profile = config.load_my_data()
    print(f"  Profile loaded ({len(profile)} characters)")

    print("\n[WORKER] Starting AI analyzer...")
    # Override timeout if specified
    if args.ai_timeout is not None:
        config.AI_REQUEST_TIMEOUT = args.ai_timeout
    analyzer = JobAnalyzer(profile)

    print("[WORKER] Starting queue processing loop...")
    _process_queue_loop(analyzer, min_rel, batch_size)


if __name__ == "__main__":
    main()