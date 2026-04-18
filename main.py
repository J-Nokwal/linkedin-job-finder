import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

import config
from scraper import LinkedInScraper
from analyzer import JobAnalyzer


def _send_to_nextjs_api(path: str, payload: object):
    api_base = config.NEXTJS_API_URL
    if not api_base:
        print("[MAIN] NEXTJS_API_URL not configured; skipping Next.js API request")
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
        print(f"[MAIN] Next.js API HTTP error at {url}: {error.code} {payload_text}")
    except urllib.error.URLError as error:
        print(f"[MAIN] Could not connect to Next.js API at {url}: {error}")
    except Exception as error:
        print(f"[MAIN] Error posting to Next.js API: {error}")
    return None


def _push_jobs_to_nextjs_api(jobs: list[dict]) -> None:
    result = _send_to_nextjs_api("/api/jobs/save", jobs)
    if not result:
        print("[MAIN] Failed to save jobs to Next.js API")
        return

    if result.get("success"):
        print(f"[MAIN] Saved {len(jobs)} jobs to Next.js API")
    else:
        print("[MAIN] Save API returned error:", result.get("error", "unknown"))


def _push_raw_jobs_to_nextjs_queue(jobs: list[dict]) -> None:
    result = _send_to_nextjs_api("/api/jobs/queue", jobs)
    if not result:
        print("[MAIN] Failed to enqueue raw jobs to Next.js queue")
        return

    if result.get("success"):
        added = result.get("added", 0)
        skipped = result.get("skipped", 0)
        print(
            f"[MAIN] Enqueued {added} raw jobs to Next.js queue"
            + (f" ({skipped} duplicates skipped)" if skipped else "")
        )
    else:
        print("[MAIN] Queue enqueue returned error:", result.get("error", "unknown"))


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
        print(f"[MAIN] Failed to complete queue item {queue_id}")
    elif not result.get("success"):
        print(f"[MAIN] Queue completion error for {queue_id}:", result.get("error", "unknown"))


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
                "[MAIN] Fit job ready:",
                result.get("role_detected", "Unknown role"),
                "@",
                result.get("company_detected", "Unknown company"),
                f"score={result.get('fit_score', 0)}",
            )
    except Exception as e:
        print(f"[MAIN] Error analyzing queue item {queue_item['id']}: {e}")


def _process_queue_loop(scraper: LinkedInScraper, analyzer: JobAnalyzer, min_rel: int) -> None:
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    print(f"[MAIN] Starting queue processor {worker_id} (sequential, 1 analysis at a time)")

    while True:
        # Claim just 1 item at a time for sequential processing
        queue_items = _claim_queue_jobs(1, worker_id)
        if not queue_items:
            print("[MAIN] Queue empty; sleeping 60 seconds and fetching new posts")
            time.sleep(60)
            continue

        item = queue_items[0]
        print(f"[MAIN] Processing queue item {item['id']}")
        _process_queue_item(analyzer, item, min_rel)
        time.sleep(0.5)  # Small delay between items


def _best_apply_url(job: dict) -> str:
    ranked = job.get("apply_links_ranked")
    if isinstance(ranked, list) and ranked:
        return str(ranked[0])
    return str(job.get("apply_link") or "")


def print_job(job: dict, index: int):
    """Print a formatted job summary."""
    role = job.get("role_detected", "Unknown Role")
    company = job.get("company_detected", "Unknown Company")
    location = job.get("location_detected", "Unknown")
    date_posted = job.get("date_posted", "Unknown date")
    score = job.get("fit_score", 0)
    relevance = job.get("job_relevance_0_100")
    reason = job.get("fit_reason") or ""
    link = _best_apply_url(job) or "no link found"
    action = job.get("action", "skip").upper()
    post_kind = (job.get("post_kind") or "").strip()

    print("\n" + "=" * 50)
    print(f"# {index} {role} @ {company}")
    kind_parts = []
    if post_kind:
        kind_parts.append(f"Kind: {post_kind}")
    if relevance is not None:
        kind_parts.append(f"job relevance {relevance}/100")
    if kind_parts:
        print(f"   {' | '.join(kind_parts)}")
    print(f"   📍 {location} | Posted: {date_posted}")
    print(f"   ✅ Fit Score: {score}/100")
    print(f"   💡 {reason}")
    reqs = job.get("requirements") or []
    if isinstance(reqs, list) and reqs:
        print("   📋 Requirements:")
        for line in reqs[:3]:
            if line:
                print(f"      • {line}")
        if len(reqs) > 3:
            print(f"      … (+{len(reqs) - 3} more)")
    print(f"   🔗 {link}")
    print(f"   ⚡ Action: {action}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="LinkedIn job finder + AI enrichment")
    parser.add_argument(
        "--min-job-relevance",
        type=int,
        default=0,
        metavar="N",
        help="Only show matching jobs with job_relevance_0_100 >= N (0–100). Default: 0.",
    )
    args = parser.parse_args()
    min_rel = max(0, min(100, args.min_job_relevance))

    print("\n" + "#" * 60)
    print("#  LINKEDIN JOB FINDER")
    print("#" * 60)

    print("\n[MAIN] Loading configuration...")
    print(f"  OpenAI Model: {config.OPENAI_MODEL}")
    print(f"  OpenAI Base URL: {config.OPENAI_BASE_URL}")
    print(f"  AI request timeout (s): {config.AI_REQUEST_TIMEOUT}")
    print(f"  AI triage first: {config.AI_TRIAGE_FIRST}")
    print(f"  Feed AI triage raw (no keyword gate): {config.FEED_AI_TRIAGE_RAW}")
    print(f"  Min job relevance (display filter): {min_rel}")
    n_kw = len([q for q in config.CONTENT_SEARCH_QUERIES if (q or "").strip()])
    print(
        f"  Search: {len(config.HASHTAGS)} hashtag(s), "
        f"{n_kw} keyword phrase(s), up to {config.POSTS_PER_HASHTAG} posts each"
    )
    fq = config.content_search_extra_query()
    if fq:
        print(f"  Content search URL filters:{fq}")

    print("\n[MAIN] Loading profile data from myData/...")
    profile = config.load_my_data()
    print(f"  Profile loaded ({len(profile)} characters)")

    print("\n[MAIN] Starting browser scraper...")
    scraper = LinkedInScraper()

    try:
        all_posts = []
        seen_keys = set()
        for post in scraper.run():
            key = scraper._post_dedupe_key(post)
            if key not in seen_keys:
                seen_keys.add(key)
                all_posts.append(post)
                if config.NEXTJS_API_URL:
                    _push_raw_jobs_to_nextjs_queue([post])
    except Exception as e:
        print(f"\n[MAIN] FATAL ERROR in scraper: {e}")
        sys.exit(1)

    if not all_posts:
        print("\n[MAIN] No posts found. Check your login and try again.")
        sys.exit(0)

    print(f"\n[MAIN] Collected {len(all_posts)} posts")
    results_file = config.get_results_filename()
    print(f"\n[MAIN] Saving raw captures to {results_file}")

    try:
        with open(results_file, "w") as f:
            json.dump(all_posts, f, indent=2)
        print("[MAIN] Raw captures saved successfully")
    except Exception as e:
        print(f"[MAIN] ERROR saving raw captures: {e}")

    if config.NEXTJS_API_URL:
        analyzer = JobAnalyzer(profile)
        print("[MAIN] Starting queue-based analysis loop in background (non-blocking)")
        # Run queue processor in background
        queue_thread = threading.Thread(
            target=_process_queue_loop,
            args=(scraper, analyzer, min_rel),
            daemon=False,
        )
        queue_thread.start()
        print("[MAIN] Queue processor running continuously")
        queue_thread.join()

    print("\n[MAIN] Starting AI analysis...")
    analyzer = JobAnalyzer(profile)

    try:
        analyzed_jobs = analyzer.analyze_all(all_posts)
    except Exception as e:
        print(f"\n[MAIN] FATAL ERROR in analyzer: {e}")
        sys.exit(1)

    def _job_relevance(j: dict) -> int:
        try:
            return int(j.get("job_relevance_0_100") or 0)
        except (TypeError, ValueError):
            return 0

    fit_jobs = [
        j
        for j in analyzed_jobs
        if j.get("is_fit", False) and _job_relevance(j) >= min_rel
    ]

    print(f"\n[MAIN] Saving all {len(analyzed_jobs)} results to {results_file}")

    try:
        with open(results_file, "w") as f:
            json.dump(analyzed_jobs, f, indent=2)
        print("[MAIN] Results saved successfully")
    except Exception as e:
        print(f"[MAIN] ERROR saving results: {e}")

    _push_jobs_to_nextjs_api(analyzed_jobs)
    print("\n" + "#" * 60)
    print("#  MATCHING JOBS FOUND")
    print(f"#  {len(fit_jobs)} of {len(analyzed_jobs)} posts pass fit + relevance filter")
    print("#" * 60)

    if fit_jobs:
        fit_jobs.sort(
            key=lambda x: (
                x.get("fit_score", 0),
                _job_relevance(x),
            ),
            reverse=True,
        )

        for i, job in enumerate(fit_jobs, 1):
            print_job(job, i)

        def _norm_action(j):
            return " ".join(str(j.get("action", "")).lower().split())

        apply_count = sum(1 for j in fit_jobs if _norm_action(j) == "apply now")
        save_count = sum(1 for j in fit_jobs if _norm_action(j) == "save for later")

        print("\n" + "=" * 50)
        print(f"SUMMARY: {apply_count} apply now | {save_count} save for later")
        print("=" * 50)
    else:
        print(
            "\n[MAIN] No fitting jobs found for this filter. "
            "Try lowering --min-job-relevance, adjusting myData/, or disabling triage."
        )

    print(f"\n[MAIN] Full results saved to: {results_file}")


if __name__ == "__main__":
    main()
