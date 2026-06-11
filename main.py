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
    result = _send_to_nextjs_api("/api/jobs/save", jobs)
    if not result:
        log.warning("Failed to save jobs to Next.js API")
        return
    if result.get("success"):
        log.success(f"Saved {len(jobs)} jobs to Next.js API")
    else:
        log.error(f"Save API returned error: {result.get('error', 'unknown')}")


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
    args = parser.parse_args()
    min_rel = max(0, min(100, args.min_job_relevance))

    log.banner("LinkedIn Job Finder", f"Platform: {config.PLATFORM.upper()}")

    log.rule("Configuration")
    if len(config.OPENAI_MODELS) > 1:
        log.kv("Models (rotating)", ", ".join(config.OPENAI_MODELS))
    else:
        log.kv("Model", config.OPENAI_MODEL)
    log.kv("Base URL",        config.OPENAI_BASE_URL)
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

    log.rule("Scraper")
    scraper = LinkedInScraper()

    try:
        all_posts = []
        seen_keys = set()
        for post in scraper.run():
            key = scraper._post_dedupe_key(post)
            if key not in seen_keys:
                seen_keys.add(key)
                all_posts.append(post)
    except Exception as e:
        log.error(f"FATAL ERROR in scraper: {e}")
        sys.exit(1)

    if not all_posts:
        log.warning("No posts found. Check your login and try again.")
        sys.exit(0)

    log.success(f"Collected [bold]{len(all_posts)}[/bold] posts")

    results_file = config.get_results_filename()
    log.info(f"Saving raw captures → {results_file}")
    try:
        with open(results_file, "w") as f:
            json.dump(all_posts, f, indent=2)
        log.success("Raw captures saved")
    except Exception as e:
        log.error(f"Failed to save raw captures: {e}")

    log.rule("AI Analysis")
    analyzer = JobAnalyzer(profile)

    try:
        analyzed_jobs = analyzer.analyze_all(all_posts)
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

    _push_jobs_to_nextjs_api(analyzed_jobs)

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
