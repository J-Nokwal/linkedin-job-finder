import json
import random
import time
from typing import Any, Dict, List

try:
    from openai import APIConnectionError, APITimeoutError, OpenAI
except ImportError:
    print("ERROR: OpenAI library not installed. Run: pip install openai")
    raise

import config


def _parse_json_from_model_text(result_text: str) -> Dict[str, Any]:
    """
    Models often prefix prose ('Here is the JSON:') or use fences; extract the first JSON object.
    """
    text = (result_text or "").strip()
    if not text:
        raise json.JSONDecodeError("empty model response", "", 0)

    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif text.count("```") >= 2:
        parts = text.split("```", 2)
        chunk = parts[1].strip()
        if chunk.lower().startswith("json"):
            chunk = chunk[4:].lstrip()
        text = chunk

    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("no JSON object start", text, 0)

    decoder = json.JSONDecoder()
    obj, _end = decoder.raw_decode(text, start)
    if not isinstance(obj, dict):
        raise TypeError("model JSON root must be an object")
    return obj


class JobAnalyzer:
    def __init__(self, profile: str):
        self.profile = profile
        self.client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            timeout=config.AI_REQUEST_TIMEOUT,
        )

    @staticmethod
    def _post_json_for_llm(post: Dict[str, Any]) -> Dict[str, Any]:
        """Subset of scrape fields sent to the model (bounded size)."""
        keys = (
            "post_text",
            "author_name",
            "author_title",
            "post_url",
            "date_posted",
            "likes_count",
            "source",
            "links",
            "external_urls",
            "linkedin_job_urls",
            "linkedin_profile_urls",
            "hashtags_in_text",
            "scraped_at",
            "activity_urn",
        )
        out: Dict[str, Any] = {}
        for k in keys:
            if k in post:
                out[k] = post[k]
        links = out.get("links") or []
        if isinstance(links, list) and len(links) > 50:
            out["links"] = links[:50]
        return out

    @staticmethod
    def _serialize_post_for_llm(post: Dict[str, Any]) -> str:
        payload = JobAnalyzer._post_json_for_llm(post)
        return json.dumps(payload, ensure_ascii=True, indent=2)

    def _chat_json(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float = 0.2,
    ) -> str:
        response = self.client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        raw = response.choices[0].message.content
        return (raw or "").strip()

    def triage_post(self, post: Dict[str, Any]) -> Dict[str, Any]:
        """Cheap pass: should we run full enrichment?"""
        post_json = self._serialize_post_for_llm(post)
        profile_head = (self.profile or "")[:2000]
        user = config.TRIAGE_USER_TEMPLATE.format(
            profile_head=profile_head,
            post_json=post_json,
        )
        result_text = self._chat_json(
            system=config.TRIAGE_SYSTEM_PROMPT,
            user=user,
            max_tokens=config.AI_MAX_TOKENS_TRIAGE,
            temperature=0.1,
        )
        if not result_text:
            return {"continue": True, "post_kind_hint": "unclear", "reason": "empty_triage"}
        try:
            return _parse_json_from_model_text(result_text)
        except (json.JSONDecodeError, TypeError, ValueError):
            return {"continue": True, "post_kind_hint": "unclear", "reason": "triage_parse_failed"}

    def enrich_post(self, post: Dict[str, Any]) -> Dict[str, Any]:
        """Full extraction + fit analysis."""
        post_json = self._serialize_post_for_llm(post)
        user = config.USER_ENRICHMENT_PROMPT_TEMPLATE.format(
            profile=self.profile,
            post_json=post_json,
        )
        result_text = self._chat_json(
            system=config.ENRICHMENT_SYSTEM_PROMPT,
            user=user,
            max_tokens=config.AI_MAX_TOKENS_ENRICH,
            temperature=0.3,
        )
        if not result_text:
            return {**post, "is_fit": False, "fit_score": 0, "action": "skip", "error": "empty_response"}

        try:
            parsed = _parse_json_from_model_text(result_text)
            merged = {**post, **parsed}
            ranked = merged.get("apply_links_ranked")
            if isinstance(ranked, list) and ranked and not merged.get("apply_link"):
                merged["apply_link"] = ranked[0]
            return merged
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            print(f"[ANALYZER] JSON parse error: {e}")
            snippet = (result_text[:500] + "…") if len(result_text) > 500 else result_text
            print(f"[ANALYZER] Raw response: {snippet}")
            return {
                **post,
                "is_fit": False,
                "fit_score": 0,
                "action": "skip",
                "error": "parse_failed",
            }

    def analyze_post(self, post: Dict[str, Any]) -> Dict[str, Any]:
        """Optional triage, then full enrich (or skip after triage)."""
        if config.AI_TRIAGE_FIRST:
            tri = self.triage_post(post)
            cont = tri.get("continue", True)
            post = {
                **post,
                "triage_continue": cont,
                "triage_post_kind_hint": tri.get("post_kind_hint"),
                "triage_reason": tri.get("reason"),
            }
            if not cont:
                return {
                    **post,
                    "triage_skipped_full_enrich": True,
                    "post_kind": tri.get("post_kind_hint") or "noise",
                    "job_relevance_0_100": 0,
                    "is_fit": False,
                    "fit_score": 0,
                    "fit_reason": tri.get("reason") or "Skipped after triage",
                    "action": "skip",
                    "requirements": [],
                    "apply_links_ranked": [],
                }

        return self.enrich_post(post)

    def analyze_all(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print("\n" + "=" * 50)
        print("ANALYZING JOBS WITH AI")
        if config.AI_TRIAGE_FIRST:
            print("(triage-first enabled)")
        print("=" * 50)

        analyzed: List[Dict[str, Any]] = []
        triage_skips = 0
        full_enriched = 0

        for i, post in enumerate(posts, 1):
            print(f"[ANALYZER] Analyzing post {i}/{len(posts)}...")

            try:
                result = self.analyze_post(post)
            except KeyboardInterrupt:
                print(
                    "\n[ANALYZER] Ctrl+C — skipping this post, continuing with the next …"
                )
                result = {
                    **post,
                    "is_fit": False,
                    "fit_score": 0,
                    "action": "skip",
                    "error": "keyboard_interrupt",
                }
            except APITimeoutError as e:
                print(
                    f"[ANALYZER] Request timed out ({e!s}). "
                    f"Set AI_REQUEST_TIMEOUT higher in .env (e.g. 600) for slow local models."
                )
                result = {
                    **post,
                    "is_fit": False,
                    "fit_score": 0,
                    "action": "skip",
                    "error": "request_timeout",
                }
            except APIConnectionError as e:
                print(f"[ANALYZER] API connection error: {e!s}")
                result = {
                    **post,
                    "is_fit": False,
                    "fit_score": 0,
                    "action": "skip",
                    "error": "connection_error",
                }
            except Exception as e:
                print(
                    f"[ANALYZER] Error on post {i}/{len(posts)} "
                    f"({type(e).__name__}): {e}"
                )
                result = {
                    **post,
                    "is_fit": False,
                    "fit_score": 0,
                    "action": "skip",
                    "error": f"analyze_error:{type(e).__name__}",
                }

            analyzed.append(result)

            if result.get("triage_skipped_full_enrich"):
                triage_skips += 1
                print(f"  ⏭ Skipped full enrich (triage): {result.get('triage_reason', '')}")
            elif result.get("error"):
                print(f"  ⚠ Skipped: {result.get('error')}")
            else:
                full_enriched += 1
                if result.get("is_fit"):
                    print(
                        f"  ✅ Fit Score: {result.get('fit_score', 0)}/100 - "
                        f"{result.get('role_detected', 'Unknown')}"
                    )
                else:
                    print("  ❌ Not a fit")

            try:
                time.sleep(random.uniform(1, 2))
            except KeyboardInterrupt:
                print(
                    "\n[ANALYZER] Ctrl+C — skipping delay before next post …"
                )

        n_err = sum(1 for r in analyzed if r.get("error"))
        print(
            f"\n[ANALYZER] Done. Full enrich: {full_enriched} | "
            f"Triage-only skips: {triage_skips} | "
            f"Errors/interrupts: {n_err}"
        )
        return analyzed
