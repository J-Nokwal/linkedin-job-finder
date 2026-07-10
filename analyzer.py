import ast
import json
import re
import time
from typing import Any, Dict, List

import config
from logger import Logger
from modules.ai.provider import (
    make_provider,
    ProviderConnectionError,
    ProviderPayloadTooLargeError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

log = Logger("ANALYZER")


def _clean_model_json_text(text: str) -> str:
    if not text:
        return text

    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif text.count("```") >= 2:
        parts = text.split("```", 2)
        chunk = parts[1].strip()
        if chunk.lower().startswith("json"):
            chunk = chunk[4:].lstrip()
        text = chunk

    text = text.strip()
    text = text.replace("None", "null")
    text = text.replace("True", "true").replace("False", "false")
    text = re.sub(r",\s*([}\]])", r"\1", text)

    return text


def _parse_json_from_model_text(result_text: str) -> Dict[str, Any]:
    text = (result_text or "").strip()
    if not text:
        raise json.JSONDecodeError("empty model response", "", 0)

    text = _clean_model_json_text(text)

    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("no JSON object start", text, 0)

    decoder = json.JSONDecoder()
    try:
        obj, _end = decoder.raw_decode(text, start)
    except json.JSONDecodeError:
        cleaned = _clean_model_json_text(text)
        try:
            obj = json.loads(cleaned[start:])
        except json.JSONDecodeError:
            try:
                obj = ast.literal_eval(cleaned[start:])
            except (ValueError, SyntaxError) as e:
                raise json.JSONDecodeError(
                    f"failed to parse model JSON: {e}", cleaned, 0
                ) from e
    if not isinstance(obj, dict):
        raise TypeError("model JSON root must be an object")
    return obj


class JobAnalyzer:
    def __init__(self, profile: str):
        self.profile = profile
        self._provider = make_provider(profile)
        log.info(
            f"Provider: [bold]{config.AI_PROVIDER.upper()}[/bold] | "
            f"Model: [bold]{self._provider.current_model()}[/bold]"
        )

    @staticmethod
    def _post_json_for_llm(post: Dict[str, Any]) -> Dict[str, Any]:
        keys = (
            "post_text", "author_name", "author_title", "post_url",
            "date_posted", "likes_count", "source", "links",
            "external_urls", "linkedin_job_urls", "linkedin_profile_urls",
            "hashtags_in_text", "scraped_at", "activity_urn",
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

    def triage_post(self, post: Dict[str, Any]) -> Dict[str, Any]:
        post_json = self._serialize_post_for_llm(post)
        result_text = self._provider.triage(post_json)
        if not result_text:
            return {"continue": True, "post_kind_hint": "unclear", "reason": "empty_triage"}
        try:
            return _parse_json_from_model_text(result_text)
        except (json.JSONDecodeError, TypeError, ValueError):
            return {"continue": True, "post_kind_hint": "unclear", "reason": "triage_parse_failed"}

    def enrich_post(self, post: Dict[str, Any]) -> Dict[str, Any]:
        post_json = self._serialize_post_for_llm(post)
        result_text = self._provider.enrich(post_json)
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
            log.error(f"JSON parse error: {e}")
            snippet = (result_text[:500] + "…") if len(result_text) > 500 else result_text
            log.debug(f"Raw response: {snippet}")
            return {
                **post,
                "is_fit": False,
                "fit_score": 0,
                "action": "skip",
                "error": "parse_failed",
            }

    def analyze_post(self, post: Dict[str, Any]) -> Dict[str, Any]:
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

    def analyze_all(self, posts: List[Dict[str, Any]], on_complete=None) -> List[Dict[str, Any]]:
        log.rule("Analyzing Jobs with AI" + (" · triage-first" if config.AI_TRIAGE_FIRST else ""))

        analyzed: List[Dict[str, Any]] = []
        triage_skips = 0
        full_enriched = 0

        for i, post in enumerate(posts, 1):
            log.info(f"Post [bold]{i}/{len(posts)}[/bold] · model: [bold]{self._provider.current_model()}[/bold]")

            n_attempts = self._provider.max_attempts()
            result = None
            last_error = "rate_limit_all_models"
            rotated_in_loop = False
            for attempt in range(n_attempts):
                try:
                    result = self.analyze_post(post)
                    break
                except ProviderRateLimitError:
                    last_error = "rate_limit_all_models"
                    log.warning(f"Rate limit on [bold]{self._provider.current_model()}[/bold] — rotating model…")
                    self._provider.advance()
                    rotated_in_loop = True
                    if attempt < n_attempts - 1:
                        time.sleep(2)
                except ProviderPayloadTooLargeError:
                    last_error = "payload_too_large"
                    log.warning(f"Payload too large on [bold]{self._provider.current_model()}[/bold] — rotating to a bigger-context model…")
                    self._provider.advance()
                    rotated_in_loop = True
                    if attempt < n_attempts - 1:
                        time.sleep(2)
                except KeyboardInterrupt:
                    log.warning("Ctrl+C — skipping this post, continuing with the next…")
                    result = {**post, "is_fit": False, "fit_score": 0, "action": "skip", "error": "keyboard_interrupt"}
                    break
                except ProviderTimeoutError as e:
                    log.error(f"Request timed out ({e!s}) — raise AI_REQUEST_TIMEOUT in .env for slow local models.")
                    result = {**post, "is_fit": False, "fit_score": 0, "action": "skip", "error": "request_timeout"}
                    break
                except ProviderConnectionError as e:
                    log.error(f"API connection error: {e!s}")
                    result = {**post, "is_fit": False, "fit_score": 0, "action": "skip", "error": "connection_error"}
                    break
                except Exception as e:
                    log.error(f"Post {i}/{len(posts)} ({type(e).__name__}): {e}")
                    result = {**post, "is_fit": False, "fit_score": 0, "action": "skip", "error": f"analyze_error:{type(e).__name__}"}
                    break

            if result is None:
                log.warning(f"All {n_attempts} model(s) failed for post {i} ({last_error}) — skipping.")
                result = {**post, "is_fit": False, "fit_score": 0, "action": "skip", "error": last_error}

            # Only round-robin to next model if no rotation already happened inside the loop.
            if not rotated_in_loop:
                self._provider.advance()
            analyzed.append(result)
            if on_complete:
                try:
                    on_complete(result)
                except Exception as cb_err:
                    log.warning(f"on_complete callback failed for post {i}: {cb_err}")

            if result.get("triage_skipped_full_enrich"):
                triage_skips += 1
                log.skip(f"Triage skipped: {result.get('triage_reason', '')}")
            elif result.get("error"):
                log.warning(f"Skipped: {result.get('error')}")
            else:
                full_enriched += 1
                if result.get("is_fit"):
                    log.success(f"Fit [bold]{result.get('fit_score', 0)}/100[/bold] — {result.get('role_detected', 'Unknown')}")
                else:
                    log.info("Not a fit")

            try:
                time.sleep(config.AI_ANALYSIS_DELAY)
            except KeyboardInterrupt:
                log.warning("Ctrl+C — skipping delay before next post…")

        n_err = sum(1 for r in analyzed if r.get("error"))
        log.rule(f"Done · enriched: {full_enriched} · triage skips: {triage_skips} · errors: {n_err}")
        return analyzed
