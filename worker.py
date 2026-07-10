import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

import config
from analyzer import JobAnalyzer
from logger import Logger

log = Logger("WORKER")


def _send_to_nextjs_api(path: str, payload: object):
    api_base = config.NEXTJS_API_URL
    if not api_base:
        log.debug("NEXTJS_API_URL not configured; skipping Next.js API request")
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
        log.error(f"Next.js API HTTP error at {url}: {error.code} {payload_text}")
    except urllib.error.URLError as error:
        log.error(f"Could not connect to Next.js API at {url}: {error}")
    except Exception as error:
        log.error(f"Error posting to Next.js API: {error}")
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
        log.warning(f"Failed to complete queue item {queue_id}")
    elif not result.get("success"):
        log.error(f"Queue completion error for {queue_id}: {result.get('error', 'unknown')}")


def _job_relevance(job: dict) -> int:
    try:
        return int(job.get("job_relevance_0_100") or 0)
    except (TypeError, ValueError):
        return 0


def _process_queue_item(analyzer: JobAnalyzer, queue_item: dict, min_rel: int) -> None:
    try:
        payload = queue_item.get("payload") or {}
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
            log.success(
                f"Fit job: {result.get('role_detected', 'Unknown')} "
                f"@ {result.get('company_detected', 'Unknown')} "
                f"score={result.get('fit_score', 0)}"
            )
    except Exception as e:
        log.error(f"Error analyzing queue item {queue_item['id']}: {e}")


def _process_queue_loop(analyzer: JobAnalyzer, min_rel: int, batch_size: int = 1) -> None:
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    log.info(f"Queue processor [bold]{worker_id}[/bold] started (batch size: {batch_size})")

    while True:
        queue_items = _claim_queue_jobs(batch_size, worker_id)
        if not queue_items:
            log.debug("Queue empty — sleeping 60s")
            time.sleep(60)
            continue

        for item in queue_items:
            log.info(f"Processing queue item [bold]{item['id']}[/bold]")
            _process_queue_item(analyzer, item, min_rel)
            time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description="LinkedIn job queue worker")
    parser.add_argument("--min-job-relevance", type=int, default=0, metavar="N")
    parser.add_argument("--batch-size",        type=int, default=1, metavar="N")
    parser.add_argument("--ai-timeout",        type=int, default=None, metavar="SECONDS")
    args = parser.parse_args()

    min_rel    = max(0, min(100, args.min_job_relevance))
    batch_size = max(1, args.batch_size)
    ai_timeout = args.ai_timeout if args.ai_timeout is not None else config.AI_REQUEST_TIMEOUT

    log.banner("LinkedIn Job Queue Worker", f"Provider: {config.AI_PROVIDER.upper()}")

    log.rule("Configuration")
    log.kv("Provider",        config.AI_PROVIDER.upper())
    if config.AI_PROVIDER == "claude":
        log.kv("Model",       config.CLAUDE_MODEL or "claude (default)")
        log.kv("Auth",        "API key" if config.ANTHROPIC_API_KEY else "Claude Code subscription")
    else:
        log.kv("Model",       config.OPENAI_MODEL)
        log.kv("Base URL",    config.OPENAI_BASE_URL)
    log.kv("Request timeout", f"{ai_timeout}s")
    log.kv("Min relevance",   str(min_rel))
    log.kv("Batch size",      str(batch_size))

    if not config.NEXTJS_API_URL:
        log.error("NEXTJS_API_URL not configured — cannot run worker.")
        sys.exit(1)

    log.rule("Profile")
    profile = config.load_my_data()
    log.success(f"Profile loaded ({len(profile)} characters)")

    log.rule("Analyzer")
    if args.ai_timeout is not None:
        config.AI_REQUEST_TIMEOUT = args.ai_timeout
    analyzer = JobAnalyzer(profile)

    log.rule("Queue Loop")
    _process_queue_loop(analyzer, min_rel, batch_size)


if __name__ == "__main__":
    main()
