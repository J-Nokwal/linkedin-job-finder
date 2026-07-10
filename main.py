import argparse
import json
import sys
import urllib.error
import urllib.request

import config
from scraper import LinkedInScraper
from analyzer import JobAnalyzer
from logger import Logger, job_card, summary_table

log = Logger("MAIN")


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


def _push_jobs_to_nextjs_api(jobs: list[dict]) -> None:
    """Direct save — used only for --skip-scrape re-analysis."""
    result = _send_to_nextjs_api("/api/jobs/save", jobs)
    if not result:
        log.warning("Failed to save jobs to Next.js API")
        return
    if result.get("success"):
        log.success(f"Saved {result.get('created', len(jobs))} jobs to Next.js API "
                    f"({result.get('skipped', 0)} already existed)")
    else:
        log.error(f"Save API returned error: {result.get('error', 'unknown')}")


def _enqueue_post(post: dict) -> str | None:
    """Enqueue a single raw post; return queue_id if newly added, None if duplicate/error."""
    result = _send_to_nextjs_api("/api/jobs/queue", [post])
    if not result or not result.get("success"):
        return None
    items = result.get("results", [])
    if not items:
        log.error(
            "Queue API returned no per-item results — "
            "Next.js build may be stale. Run: cd nextjs && npm run build"
        )
        return None
    r = items[0]
    return r.get("id") if r.get("queued") else None


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


def _best_apply_url(job: dict) -> str:
    ranked = job.get("apply_links_ranked")
    if isinstance(ranked, list) and ranked:
        return str(ranked[0])
    return str(job.get("apply_link") or "")


def main():
    parser = argparse.ArgumentParser(description="LinkedIn job finder + AI enrichment")
    parser.add_argument(
        "--min-job-relevance",
        type=int,
        default=0,
        metavar="N",
        help="Only show matching jobs with job_relevance_0_100 >= N (0–100). Default: 0.",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip scraping; load posts from the most recent results JSON file and re-analyse.",
    )
    args = parser.parse_args()
    min_rel = max(0, min(100, args.min_job_relevance))

    provider_label = config.AI_PROVIDER.upper()
    log.banner("LinkedIn Job Finder", f"Provider: {provider_label}")

    log.rule("Configuration")
    log.kv("Provider", provider_label)
    if config.AI_PROVIDER == "claude":
        log.kv("Model", config.CLAUDE_MODEL or "claude (default)")
        log.kv("Auth",  "API key" if config.ANTHROPIC_API_KEY else "Claude Code subscription")
    else:
        if len(config.OPENAI_MODELS) > 1:
            log.kv("Models (rotating)", ", ".join(config.OPENAI_MODELS))
        else:
            log.kv("Model", config.OPENAI_MODEL)
        log.kv("Base URL", config.OPENAI_BASE_URL)
    log.kv("Request timeout", f"{config.AI_REQUEST_TIMEOUT}s")
    log.kv("Analysis delay",  f"{config.AI_ANALYSIS_DELAY}s")
    log.kv("Triage first",    str(config.AI_TRIAGE_FIRST))
    log.kv("Feed AI triage",  str(config.FEED_AI_TRIAGE_RAW))
    log.kv("Min relevance",   str(min_rel))
    n_kw = len([q for q in config.CONTENT_SEARCH_QUERIES if (q or "").strip()])
    log.kv("Search",
           f"{len(config.HASHTAGS)} hashtag(s), {n_kw} keyword phrase(s), "
           f"up to {config.POSTS_PER_HASHTAG} posts each")
    fq = config.content_search_extra_query()
    if fq:
        log.kv("URL filters", fq)

    log.rule("Profile")
    profile = config.load_my_data()
    log.success(f"Profile loaded ({len(profile)} characters)")

    results_file = config.get_results_filename()

    if args.skip_scrape:
        log.rule("Analyser-only mode (--skip-scrape)")
        # Find the most recent results file to re-analyse.
        candidate = results_file if results_file.exists() else None
        if candidate is None:
            files = sorted(config.RESULTS_DIR.glob("jobs_*.json"), reverse=True)
            candidate = files[0] if files else None
        if candidate is None:
            log.error("No results files found. Run without --skip-scrape to scrape first.")
            sys.exit(1)
        log.info(f"Loading posts from [bold]{candidate.name}[/bold]")
        try:
            with open(candidate) as f:
                all_posts = json.load(f)
            if not isinstance(all_posts, list):
                all_posts = [all_posts]
        except Exception as e:
            log.error(f"Failed to load {candidate}: {e}")
            sys.exit(1)
        log.success(f"Loaded [bold]{len(all_posts)}[/bold] posts")
        results_file = candidate
    else:
        log.rule("Scraper")
        scraper = LinkedInScraper()

        all_posts: list[dict] = []
        queued_pairs: list[tuple[dict, str]] = []
        seen_keys: set[str] = set()
        n_dup = 0

        try:
            for post in scraper.run():
                key = scraper._post_dedupe_key(post)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_posts.append(post)
                if config.NEXTJS_API_URL:
                    queue_id = _enqueue_post(post)
                    if queue_id:
                        queued_pairs.append((post, queue_id))
                    else:
                        n_dup += 1
        except Exception as e:
            log.error(f"FATAL ERROR in scraper: {e}")
            sys.exit(1)

        if not all_posts:
            log.warning("No posts found. Check your login and try again.")
            sys.exit(0)

        log.success(
            f"Collected [bold]{len(all_posts)}[/bold] posts — "
            f"[bold]{len(queued_pairs)}[/bold] new, {n_dup} already in database"
            if config.NEXTJS_API_URL else
            f"Collected [bold]{len(all_posts)}[/bold] posts"
        )

        log.info(f"Saving raw captures → {results_file}")
        try:
            with open(results_file, "w") as f:
                json.dump(all_posts, f, indent=2)
            log.success("Raw captures saved")
        except Exception as e:
            log.error(f"Failed to save raw captures: {e}")

    log.rule("AI Analysis")
    analyzer = JobAnalyzer(profile)

    if args.skip_scrape or not config.NEXTJS_API_URL:
        # --skip-scrape: re-analyse from file, push results directly (no queue).
        # No NEXTJS_API_URL: analyse everything, results go to JSON only.
        try:
            analyzed_jobs = analyzer.analyze_all(all_posts)
        except Exception as e:
            log.error(f"FATAL ERROR in analyzer: {e}")
            sys.exit(1)
        if config.NEXTJS_API_URL:
            _push_jobs_to_nextjs_api(analyzed_jobs)
    else:
        # Normal flow: posts were enqueued as scraped; complete each one after analysis.
        if not queued_pairs:
            log.info("No new posts to analyse — all already exist in the database.")
            analyzed_jobs = []
        else:
            posts_to_analyze = [p for p, _ in queued_pairs]
            queue_ids = [qid for _, qid in queued_pairs]
            complete_idx = [0]

            def _on_complete(result: dict) -> None:
                _complete_queue_job(queue_ids[complete_idx[0]], result)
                complete_idx[0] += 1

            try:
                analyzed_jobs = analyzer.analyze_all(posts_to_analyze, on_complete=_on_complete)
            except Exception as e:
                log.error(f"FATAL ERROR in analyzer: {e}")
                sys.exit(1)

    fit_jobs = [
        j for j in analyzed_jobs
        if j.get("is_fit", False) and _job_relevance(j) >= min_rel
    ]

    log.info(f"Saving {len(analyzed_jobs)} results → {results_file}")
    try:
        with open(results_file, "w") as f:
            json.dump(analyzed_jobs, f, indent=2)
        log.success("Results saved")
    except Exception as e:
        log.error(f"Failed to save results: {e}")

    log.rule(f"Matching Jobs — {len(fit_jobs)} of {len(analyzed_jobs)} pass filter")

    if fit_jobs:
        fit_jobs.sort(
            key=lambda x: (x.get("fit_score", 0), _job_relevance(x)),
            reverse=True,
        )
        for i, job in enumerate(fit_jobs, 1):
            job_card(i, job)

        def _norm_action(j):
            return " ".join(str(j.get("action", "")).lower().split())

        apply_count = sum(1 for j in fit_jobs if _norm_action(j) == "apply now")
        save_count  = sum(1 for j in fit_jobs if _norm_action(j) == "save for later")

        summary_table(fit_jobs)
        log.rule(f"Summary · apply now: {apply_count} · save for later: {save_count}")
    else:
        log.warning(
            "No fitting jobs found. "
            "Try lowering --min-job-relevance, adjusting myData/, or disabling triage."
        )

    log.success(f"Full results → {results_file}")


if __name__ == "__main__":
    main()
