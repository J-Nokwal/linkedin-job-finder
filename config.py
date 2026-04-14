from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv
import os

# Load .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)


def _env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)).strip())
    except ValueError:
        return default

# LinkedIn credentials
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "llama3")
AI_MAX_TOKENS_ENRICH = _env_int("AI_MAX_TOKENS_ENRICH", 1600)
AI_MAX_TOKENS_TRIAGE = _env_int("AI_MAX_TOKENS_TRIAGE", 180)
AI_TRIAGE_FIRST = _env_bool("AI_TRIAGE_FIRST", False)
# Per-request HTTP timeout (seconds). Local Ollama with llama3 + large prompts often needs 180–600+.
AI_REQUEST_TIMEOUT = _env_int("AI_REQUEST_TIMEOUT", 300)
AI_CONCURRENT_ANALYSES = _env_int("AI_CONCURRENT_ANALYSES", 3)
QUEUE_CLAIM_BATCH_SIZE = _env_int("QUEUE_CLAIM_BATCH_SIZE", 6)
NEXTJS_API_URL = os.getenv("NEXTJS_API_URL", "").strip()
# When true, feed scrape skips hiring-keyword gate (more cards; use AI triage downstream).
# Default true: most feed posts do not literally contain "hiring"/"#hiring" in the scraped body.
FEED_AI_TRIAGE_RAW = _env_bool("FEED_AI_TRIAGE_RAW", True)

# Chrome profile directory
CHROME_PROFILE_DIR = os.getenv("CHROME_PROFILE_DIR", "./browser_profile")

# Results directory
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Hashtags to search (#tag → content search)
HASHTAGS = [
    "hiring",
    # "nowhiring",
    # "jobopening",
    # "opportunity"
]

# Plain keyword / phrase searches (no #); LinkedIn content search, URL-encoded.
CONTENT_SEARCH_QUERIES = [
    "Flutter developer",
    "Go (Golang)",
    "Next JS",
    "Node JS",
    # "React JS",
    # "Python",
    # "JavaScript",
    # "Dart",
    # "AWS",
    # "Dart developer",
    # "HTML5",
    # "Mobile Development",
    # "Backend & Cloud",
    # "DynamoDB",
    # "Serverless Architecture",
    # "Docker",
    # "SQL",
    # "NoSQL (DynamoDB)",
]

# Scraper settings
FEED_SCROLL_COUNT = 4
FEED_SCROLL_DELAY = 2  # seconds
HASHTAG_SCROLL_COUNT = 4  # search results lazy-load; body scroll does not load more
POSTS_PER_HASHTAG = 20  # max posts collected per hashtag OR per content query below
ACTION_DELAY_MIN = 2  # seconds
ACTION_DELAY_MAX = 3  # seconds

# LinkedIn /search/results/content/ facet filters (JSON-like values, URL-encoded).
# Example: datePosted=["past-week"]  contentType=["jobs"]
# Set to "" to omit a filter.
# contentType=["jobs"] shows LinkedIn job *listing* UI — not the post-card DOM this scraper targets.
SEARCH_FILTER_DATE_POSTED = '["past-week"]'
SEARCH_FILTER_CONTENT_TYPE = os.getenv("SEARCH_FILTER_CONTENT_TYPE", "jobs").strip()


def content_search_extra_query() -> str:
    """Extra &key=value… for content search URLs (hashtag + keyword)."""
    parts = []
    dp = (SEARCH_FILTER_DATE_POSTED or "").strip()
    if dp:
        parts.append("datePosted=" + quote(dp, safe=""))
    ct = (SEARCH_FILTER_CONTENT_TYPE or "").strip()
    if ct:
        parts.append("contentType=" + quote(ct, safe=""))
    return ("&" + "&".join(parts)) if parts else ""

# AI prompt settings
SYSTEM_PROMPT = """You are a career advisor AI. Based on the user's profile, analyze each LinkedIn job post and return ONLY valid JSON."""

USER_PROMPT_TEMPLATE = """USER PROFILE:
{profile}

JOB POST:
{post_text}

Return JSON with these exact fields:
{{
  "is_fit": true/false,
  "fit_score": 0-100,
  "fit_reason": "one sentence why",
  "role_detected": "job title if found",
  "company_detected": "company name if found",
  "location_detected": "location or remote",
  "apply_link": "URL if found in post else null",
  "date_posted": "date string",
  "skills_matched": ["skill1", "skill2"],
  "skills_missing": ["skill1"],
  "action": "apply now / save for later / skip"
}}"""

ENRICHMENT_SYSTEM_PROMPT = """You are a career advisor AI. You receive structured JSON from a LinkedIn scraper (text, links, URLs) plus the candidate profile.
Return ONLY one valid JSON object. Never invent URLs: every URL in apply_links_ranked and apply_link must appear in the provided links, external_urls, linkedin_job_urls, or post_url fields."""

TRIAGE_SYSTEM_PROMPT = """You triage LinkedIn feed cards. Return ONLY one small JSON object, no markdown."""

TRIAGE_USER_TEMPLATE = """Decide if this post is worth a full job-extraction pass for the candidate.

USER_PROFILE_SUMMARY (first 2000 chars):
{profile_head}

POST_JSON:
{post_json}

Return ONLY JSON with this shape:
{{
  "continue": true or false,
  "post_kind_hint": "job_listing" | "recruiter_promo" | "noise" | "unclear",
  "reason": "short phrase"
}}

continue=true if the post likely describes a job opening, hiring intent, or a role the user should evaluate. continue=false for ads, polls, generic engagement, or clearly unrelated content."""

USER_ENRICHMENT_PROMPT_TEMPLATE = """USER PROFILE:
{profile}

SCRAPED_POST_JSON:
{post_json}

Return ONLY one JSON object with these keys (use null for unknown scalars, [] for empty arrays, false for unknown booleans only where specified):
{{
  "post_kind": "job_listing" | "recruiter_promo" | "noise" | "other",
  "job_relevance_0_100": 0-100,
  "is_fit": true/false,
  "fit_score": 0-100,
  "fit_reason": "one sentence",
  "role_detected": "string or null",
  "company_detected": "string or null",
  "location_detected": "string or null",
  "employment_type": "full-time|part-time|contract|internship|unknown|null",
  "seniority": "intern|junior|mid|senior|lead|manager|unknown|null",
  "salary_or_comp_mentioned": "string or null",
  "date_posted": "string or null",
  "requirements": ["explicit requirement strings from the post"],
  "requirements_nice_to_have": ["optional strings"],
  "apply_links_ranked": ["best apply URLs first; each MUST appear in input links or URL fields"],
  "apply_link": "single best URL or null; must match an input URL",
  "skills_matched": ["skill"],
  "skills_missing": ["skill"],
  "red_flags": ["short strings if any"],
  "next_step_for_candidate": "one short sentence",
  "action": "apply now" | "save for later" | "skip"
}}"""


def load_my_data():
    """Load all myData files and combine into a single profile string."""
    mydata_dir = Path(__file__).parent / "myData"
    combined = []

    for filename in ["profile.txt", "projects.txt", "preferences.txt", "resume_summary.txt"]:
        filepath = mydata_dir / filename
        if filepath.exists():
            combined.append(f"=== {filename} ===\n{filepath.read_text().strip()}")
        else:
            combined.append(f"=== {filename} ===\n[File not found]")

    return "\n\n".join(combined)


def get_results_filename():
    """Get filename for today's results."""
    from datetime import date
    return RESULTS_DIR / f"jobs_{date.today().isoformat()}.json"