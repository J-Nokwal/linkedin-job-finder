import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import quote, urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple, Generator

# region agent log
_PROJECT_ROOT = Path(__file__).resolve().parent
_AGENT_DBG_LOG = _PROJECT_ROOT / ".cursor" / "debug-0d2521.log"
_AGENT_INGEST_URL = (
    "http://127.0.0.1:7861/ingest/a68f6141-29ef-4ee4-9baa-269b6cc22f81"
)


def _agent_dbg(
    location: str,
    message: str,
    data: Dict[str, Any],
    hypothesis_id: str,
    run_id: str = "post-fix",
) -> None:
    payload = {
        "sessionId": "0d2521",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    line = json.dumps(payload, default=str) + "\n"
    try:
        req = urllib.request.Request(
            _AGENT_INGEST_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Debug-Session-Id": "0d2521",
            },
        )
        with urllib.request.urlopen(req, timeout=0.45) as resp:
            resp.read(64)
    except (urllib.error.URLError, TimeoutError, OSError):
        pass

    try:
        _AGENT_DBG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_AGENT_DBG_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        print(
            f"[SCRAPER] Debug log write failed: {_AGENT_DBG_LOG}: {type(e).__name__}",
            file=sys.stderr,
        )


# endregion

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: Playwright not installed. Run: pip install playwright && playwright install chromium")
    raise

import config


class LinkedInScraper:
    def __init__(self):
        self.posts: List[Dict[str, Any]] = []
        self.browser = None
        self.context = None
        self.page = None
        self._playwright = None

    def launch_browser(self):
        """Launch Chromium with persistent session."""
        profile_path = Path(config.CHROME_PROFILE_DIR).resolve()
        profile_path.mkdir(parents=True, exist_ok=True)

        print(f"[SCRAPER] Launching Chromium with profile at: {profile_path}")

        self._playwright = sync_playwright().start()
        try:
            self.browser = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_path),
                headless=False,
                viewport={"width": 1366, "height": 864},
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception:
            self._playwright.stop()
            self._playwright = None
            raise

        self.context = self.browser
        deadline = time.time() + 5.0
        while time.time() < deadline and not self.browser.pages:
            time.sleep(0.05)
        if self.browser.pages:
            self.page = self.browser.pages[0]
        else:
            self.page = self.browser.new_page()
        print("[SCRAPER] Browser launched successfully")

    def login(self):
        """Check if logged in, if not perform login."""
        print("[SCRAPER] Checking LinkedIn login status...")
        self.page.goto("https://www.linkedin.com/", timeout=30000)
        self.page.wait_for_load_state("domcontentloaded")
        time.sleep(2)

        if self._is_logged_in():
            print("[SCRAPER] Already logged in, session preserved")
            return

        print("[SCRAPER] Not logged in, performing login...")

        self.page.goto("https://www.linkedin.com/login", timeout=30000)
        self.page.wait_for_load_state("domcontentloaded")
        time.sleep(3)

        # Check if we got redirected away from login page (already logged in)
        if not self._is_on_login_page():
            print("[SCRAPER] Redirected from login page, re-checking login status...")
            if self._is_logged_in():
                print("[SCRAPER] Actually logged in, session preserved")
                return
            # If still not logged in, we have a real problem
            print("[SCRAPER] ERROR: Not on login page and not logged in")
            self._save_screenshot("login_page_error")
            raise Exception("Cannot reach LinkedIn login page")

        try:
            email_input = self.page.wait_for_selector("#username", timeout=10000)
            email_input.fill(config.LINKEDIN_EMAIL)
            time.sleep(random.uniform(config.ACTION_DELAY_MIN, config.ACTION_DELAY_MAX))

            password_input = self.page.wait_for_selector("#password", timeout=10000)
            password_input.fill(config.LINKEDIN_PASSWORD)
            time.sleep(random.uniform(config.ACTION_DELAY_MIN, config.ACTION_DELAY_MAX))

            self.page.click('button[type="submit"]')
            self.page.wait_for_load_state("domcontentloaded")
            time.sleep(3)

            self._check_verification()

            if self._is_logged_in():
                print("[SCRAPER] Login successful")
            else:
                print("[SCRAPER] Login may have failed, please check manually")

        except Exception as e:
            print(f"[SCRAPER] ERROR during login: {e}")
            self._save_screenshot("login_error")
            raise

    def _auth_blocked_url(self) -> bool:
        u = (self.page.url or "").lower()
        return "linkedin.com/login" in u or "checkpoint" in u or "challenge" in u

    def _url_suggests_logged_in(self) -> bool:
        """LinkedIn often redirects /login → /feed when a session already exists."""
        if self._auth_blocked_url():
            return False
        u = (self.page.url or "").lower()
        path_markers = (
            "/feed/",
            "/mynetwork/",
            "/messaging/",
            "/notifications/",
            "/jobs/collections/",
            "/sales/",
            "/learning/",
        )
        return any(m in u for m in path_markers)

    def _is_on_login_page(self) -> bool:
        """True if the email/password form is present (LinkedIn sometimes changes wrappers)."""
        login_field_selectors = [
            "#username",
            'input[name="session_key"]',
            'input[id="username"]',
            "#session_key",
        ]
        for sel in login_field_selectors:
            try:
                if self.page.locator(sel).first.is_visible(timeout=2000):
                    return True
            except Exception:
                continue
        return False

    def _is_logged_in(self) -> bool:
        """Detect an authenticated session via URL (reliable) then common feed / nav UI."""
        if self._url_suggests_logged_in():
            return True

        dom_hints = [
            ".global-nav",
            "header.global-nav",
            '[class*="global-nav__"]',
            ".feed-identity-module",
            ".profile-rail-card",
            '[data-test-id="main-nav"]',
            ".scaffold-layout__list",
            "article.feed-shared-update-v2",
        ]
        for sel in dom_hints:
            try:
                loc = self.page.locator(sel).first
                if loc.is_visible(timeout=2500):
                    return True
            except Exception:
                continue

        # Wording LinkedIn keeps fairly stable on the home feed (avoid "Search" — present when logged out too)
        for locator in (
            self.page.get_by_text("Start a post", exact=True),
            self.page.get_by_role("button", name="Start a post"),
        ):
            try:
                if locator.first.is_visible(timeout=2000):
                    return True
            except Exception:
                continue

        return False

    def _check_verification(self):
        """Check for CAPTCHA or verification screen."""
        try:
            page_content = self.page.content().lower()
            if "captcha" in page_content or "verification" in page_content or "verify" in page_content:
                print("\n" + "=" * 60)
                print("MANUAL ACTION REQUIRED")
                print("LinkedIn is showing a CAPTCHA or verification screen.")
                print("Please complete the verification in the browser window.")
                print("Press ENTER when done...")
                print("=" * 60)
                input()
        except Exception:
            pass

    def _random_delay(self):
        """Add random delay between actions."""
        delay = random.uniform(config.ACTION_DELAY_MIN, config.ACTION_DELAY_MAX)
        time.sleep(delay)

    def _save_screenshot(self, name: str):
        """Save screenshot for debugging."""
        try:
            screenshot_dir = Path(config.RESULTS_DIR) / "screenshots"
            screenshot_dir.mkdir(exist_ok=True, parents=True)
            self.page.screenshot(path=str(screenshot_dir / f"{name}.png"))
            print(f"[SCRAPER] Screenshot saved: {name}.png")
        except Exception as e:
            print(f"[SCRAPER] Failed to save screenshot: {e}")

    _LINKEDIN_COLUMN_SCROLL_JS = """
            () => {
                function pick() {
                    const selectors = [
                        ".scaffold-layout__main",
                        "main.scaffold-layout__main",
                        "main[role='main']",
                        ".search-results-container",
                        ".scaffold-layout__list-container",
                        ".search-results__cluster-content",
                    ];
                    for (const s of selectors) {
                        const el = document.querySelector(s);
                        if (el && el.scrollHeight > el.clientHeight + 50) return el;
                    }
                    const main = document.querySelector("main");
                    if (main && main.scrollHeight > main.clientHeight + 50) return main;
                    return document.scrollingElement || document.documentElement;
                }
                const el = pick();
                const step = Math.max(400, Math.floor((el.clientHeight || window.innerHeight) * 0.88));
                el.scrollTop = Math.min(el.scrollTop + step, el.scrollHeight);
            }
            """

    def _iter_scrape_frames(self):
        """Main frame first, then embedded frames (feed/search sometimes render inside iframes)."""
        mf = self.page.main_frame
        yield mf
        for fr in self.page.frames:
            if fr is not mf:
                yield fr

    def _scroll_linkedin_main(self) -> None:
        """Scroll LinkedIn's main column in every frame; body scroll alone often does nothing."""
        for fr in self._iter_scrape_frames():
            try:
                fr.evaluate(self._LINKEDIN_COLUMN_SCROLL_JS)
            except Exception:
                continue

    def _wheel_scroll_fallback(self) -> None:
        """Some LinkedIn layouts respond better to wheel events at the viewport center."""
        vs = self.page.viewport_size
        if vs:
            x = max(vs["width"] // 2, 120)
            y = max(vs["height"] // 2, 120)
        else:
            x, y = 700, 500
        self.page.mouse.move(x, y)
        self.page.mouse.wheel(0, 850)

    @staticmethod
    def _card_dedupe_key(el) -> str:
        """Stable key so nested nodes for the same post collapse to one card."""
        try:
            return el.evaluate(
                """e => {
                    const attrs = ['data-urn', 'data-id', 'data-activity-urn'];
                    let n = e;
                    for (let i = 0; i < 14 && n; i++) {
                        for (const a of attrs) {
                            const u = n.getAttribute && n.getAttribute(a);
                            if (u && u.includes('urn:li:activity')) return u;
                            if (u && u.includes('urn:li:ugcPost')) return u;
                        }
                        n = n.parentElement;
                    }
                    const r = e.getBoundingClientRect();
                    return 'pos:' + Math.round(r.top) + ':' + Math.round(r.left);
                }"""
            )
        except Exception:
            return str(id(el))

    _ACTIVITY_HREF_RE = re.compile(
        r"activity(?:%3A|%3a|:)(\d+)", re.IGNORECASE
    )
    _ACTIVITY_DASH_RE = re.compile(r"activity-(\d{8,})", re.IGNORECASE)
    _UGCPOST_HREF_RE = re.compile(
        r"ugcPost(?:%3A|%3a|:)(\d+)", re.IGNORECASE
    )

    @classmethod
    def _activity_id_from_href(cls, href: str) -> str:
        if not href:
            return ""
        m = cls._ACTIVITY_HREF_RE.search(href)
        if m:
            return m.group(1)
        m2 = cls._ACTIVITY_DASH_RE.search(href)
        if m2:
            return m2.group(1)
        m3 = cls._UGCPOST_HREF_RE.search(href)
        if m3:
            return f"ugc:{m3.group(1)}"
        hl = href.lower()
        if "activity" in hl or "feed/update" in hl or "/posts/" in hl:
            nums = re.findall(r"\d{12,}", href)
            if nums:
                return nums[-1]
        return ""

    def _list_cards_via_activity_links(self) -> List[Tuple[str, Any]]:
        """
        LinkedIn often drops feed-shared class substrings; activity permalinks
        in <a href> remain stable across redesigns.
        Returns (href_dedupe_id, card_root_element).
        """
        sel = (
            'a[href*="urn:li:activity"], a[href*="urn%3Ali%3Aactivity"], '
            'a[href*="/feed/update/"], a[href*="feed/update"], '
            'a[href*="/posts/"]'
        )
        seen_act: set = set()
        out: List[Tuple[str, Any]] = []
        climb_js = """el => {
            const c1 = el.closest(
                '[data-urn*="urn:li:activity"],[data-urn*="urn:li:ugcPost"],' +
                '[data-id*="urn:li:activity"],[data-id*="urn:li:ugcPost"]'
            );
            if (c1) return c1;
            const c2 = el.closest(
                '[data-occludable-update-id*="activity"],' +
                '[data-occludable-update-id*="ugcPost"]'
            );
            if (c2) return c2;
            const c3 = el.closest(
                '[data-view-name="feed-full-update"],' +
                '[data-view-name="feed-detail-update"],' +
                '[data-view-name="search-entity-result-universal-template"]'
            );
            if (c3) return c3;
            const c4 = el.closest('li.profile-creator-shared-feed-update__container');
            if (c4) return c4;
            let n = el;
            for (let i = 0; i < 26 && n; i++) {
                if (n.getAttribute && n.getAttribute('role') === 'article') return n;
                n = n.parentElement;
            }
            n = el;
            for (let i = 0; i < 22 && n; i++) {
                n = n.parentElement;
                if (!n || n.tagName !== 'DIV') continue;
                const r = n.getBoundingClientRect();
                if (r.height >= 130 && r.height <= 1700 && r.width >= 300) return n;
            }
            return el.parentElement || el;
        }"""
        for fr in self._iter_scrape_frames():
            try:
                for link in fr.query_selector_all(sel):
                    try:
                        href = link.get_attribute("href") or ""
                        aid = self._activity_id_from_href(href)
                        if not aid:
                            base = self._absolute_url(href).split("?", 1)[0].strip()
                            if len(base) > 24:
                                aid = "u:" + base[-180:]
                        if not aid or aid in seen_act:
                            continue
                        handle = link.evaluate_handle(climb_js)
                        try:
                            eh = handle.as_element() if handle else None
                        except Exception:
                            eh = None
                        if not eh:
                            continue
                        seen_act.add(aid)
                        out.append((aid, eh))
                    except Exception:
                        continue
            except Exception:
                continue
        return out

    def _list_post_cards(self):
        """
        LinkedIn uses div.feed-shared-update-v2 more often than article.*;
        search content uses li.reusable-search__result-container.
        Posts may live in child iframes, so we query every frame.
        """
        selectors = [
            "[data-test-post-container]",
            "div.feed-shared-update-v2",
            "article.feed-shared-update-v2",
            "li.reusable-search__result-container",
            'div[data-urn*="urn:li:activity"]',
            '[data-id*="urn:li:activity"]',
            "li.artdeco-card.occludable-update",
            "[data-view-name='feed-full-update']",
            "li.profile-creator-shared-feed-update__container",
            '[data-view-name="search-entity-result-universal-template"]',
            "div[data-chameleon-result-urn]",
            "[role='listitem']",
            "[componentkey*='FeedType_FLAGSHIP_SEARCH']",
        ]
        seen_keys: set = set()
        out: List[Any] = []
        for fr in self._iter_scrape_frames():
            for sel in selectors:
                try:
                    for el in fr.query_selector_all(sel):
                        try:
                            key = self._card_dedupe_key(el)
                            if key in seen_keys:
                                continue
                            seen_keys.add(key)
                            out.append(el)
                        except Exception:
                            continue
                except Exception:
                    continue
        if not out:
            for fr in self._iter_scrape_frames():
                try:
                    for el in fr.query_selector_all(
                        "main article, main [role='article']"
                    ):
                        key = self._card_dedupe_key(el)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        out.append(el)
                except Exception:
                    pass
        if not out:
            for aid, el in self._list_cards_via_activity_links():
                try:
                    key = f"href:{aid}" if aid else self._card_dedupe_key(el)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    out.append(el)
                except Exception:
                    continue
        if not out:
            try:
                loc = self.page.locator("div.feed-shared-update-v2")
                n = min(loc.count(), 200)
                for i in range(n):
                    try:
                        h = loc.nth(i).element_handle(timeout=2000)
                        if not h:
                            continue
                        key = self._card_dedupe_key(h)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        out.append(h)
                    except Exception:
                        continue
            except Exception:
                pass
        return out

    def _dom_selector_counts(self) -> Dict[str, Any]:
        """Debug: selector hits summed across all frames; frame_count for context (no PII)."""
        keys = [
            "[data-test-post-container]",
            "div.feed-shared-update-v2",
            "article.feed-shared-update-v2",
            "li.reusable-search__result-container",
            'div[data-urn*="urn:li:activity"]',
            '[data-id*="urn:li:activity"]',
            "li.artdeco-card.occludable-update",
            "main article",
            "main [role='article']",
            '[data-view-name="search-entity-result-universal-template"]',
            "div[data-chameleon-result-urn]",
        ]
        out: Dict[str, int] = {k: 0 for k in keys}
        n_frames = 0
        for fr in self._iter_scrape_frames():
            n_frames += 1
            for sel in keys:
                try:
                    out[sel] += len(fr.query_selector_all(sel))
                except Exception:
                    out[sel] = -1
        try:
            loc_n = self.page.locator("div.feed-shared-update-v2").count()
        except Exception:
            loc_n = -1
        act_sel = (
            'a[href*="urn:li:activity"], a[href*="urn%3Ali%3Aactivity"], '
            'a[href*="/feed/update/"], a[href*="feed/update"], '
            'a[href*="/posts/"]'
        )
        act_links = 0
        for fr in self._iter_scrape_frames():
            try:
                act_links += len(fr.query_selector_all(act_sel))
            except Exception:
                act_links = -1
                break
        return {
            "frame_count": n_frames,
            "selector_sums": out,
            "locator_feed_shared_div": loc_n,
            "activity_href_links": act_links,
        }

    def _query_vs_locator_probe(self) -> Dict[str, Any]:
        """
        query_selector_all does not pierce open shadow roots; Frame.locator does.
        Compare per-frame to test H1 (shadow) vs H2 (wrong frame) vs H3 (stale selectors).
        """
        sel_pairs = [
            ("feed_shared_div", "div.feed-shared-update-v2"),
            ("feed_shared_class", '[class*="feed-shared"]'),
            ("main_article_role", "main [role='article']"),
            ("reusable_search_li", "li.reusable-search__result-container"),
            (
                "activity_links",
                'a[href*="urn:li:activity"], a[href*="urn%3Ali%3Aactivity"], '
                'a[href*="/feed/update/"], a[href*="feed/update"], '
                'a[href*="/posts/"]',
            ),
            (
                "search_entity_tpl",
                '[data-view-name="search-entity-result-universal-template"]',
            ),
        ]
        per_frame: List[Dict[str, Any]] = []
        for idx, fr in enumerate(self._iter_scrape_frames()):
            row: Dict[str, Any] = {
                "idx": idx,
                "is_main": fr is self.page.main_frame,
            }
            try:
                row["path_tail"] = (urlparse(fr.url or "").path or "")[-72:]
            except Exception:
                row["path_tail"] = ""
            counts: Dict[str, Any] = {}
            for label, s in sel_pairs:
                qs_n, loc_n = -1, -1
                try:
                    qs_n = len(fr.query_selector_all(s))
                except Exception:
                    qs_n = -1
                try:
                    loc_n = fr.locator(s).count()
                except Exception:
                    loc_n = -1
                counts[label] = {"qs": qs_n, "loc": loc_n}
            row["c"] = counts
            per_frame.append(row)
            if len(per_frame) >= 14:
                break
        return {"per_frame": per_frame}

    def _linkedin_dom_probe_main(self) -> Dict[str, int]:
        """Lightweight main-document shape check (no PII)."""
        try:
            return self.page.evaluate(
                """() => ({
                    iframes: document.querySelectorAll('iframe').length,
                    feedSharedClass: document.querySelectorAll('[class*="feed-shared"]').length,
                    scaffoldMain: document.querySelectorAll('.scaffold-layout__main').length,
                })"""
            )
        except Exception:
            return {}

    def _linkedin_shell_probe(self) -> Dict[str, Any]:
        """Sizes only — detects empty / non-hydrated shell (no PII)."""
        try:
            return self.page.evaluate(
                """() => {
                    const main = document.querySelector('main');
                    return {
                        bodyTextLen: (document.body && document.body.innerText)
                            ? document.body.innerText.length : 0,
                        mainHtmlLen: main && main.innerHTML ? main.innerHTML.length : 0,
                        hasFiniteScrollHotkey: !!document.querySelector(
                            '[data-finite-scroll-hotkey]'
                        ),
                    };
                }"""
            )
        except Exception:
            return {}

    def _wait_feed_shell_hydrated(self, timeout_ms: int = 60000) -> bool:
        """LinkedIn is a SPA; without layout viewport it may never mount feed nodes."""
        try:
            self.page.wait_for_function(
                """() => {
                    const q = (s) => document.querySelector(s);
                    return !!(
                        q('[class*="feed-shared"]') ||
                        q('.scaffold-layout__main') ||
                        q('[data-test-post-container]') ||
                        q('[data-view-name="feed-full-update"]') ||
                        q('.search-results-container') ||
                        q('.search-results__list') ||
                        q('.reusable-search__result-container') ||
                        q('[role="listitem"]') ||
                        q('[componentkey*="FeedType_FLAGSHIP_SEARCH"]') ||
                        (q('main') && q('main').innerHTML &&
                            q('main').innerHTML.length > 800)
                    );
                }""",
                timeout=timeout_ms,
            )
            return True
        except Exception:
            return False

    def _expand_see_more_in_card(self, root, max_clicks: int = 6) -> int:
        """Expand truncated body inside one post (… see more)."""
        if root is None:
            return 0

        selectors = [
            "button.feed-shared-inline-show-more-text__see-more--full-width",
            "button.feed-shared-inline-show-more-text__see-more",
            "span.feed-shared-inline-show-more-text__see-more",
            ".feed-shared-inline-show-more-text__see-more-less-toggle",
            "button[aria-label*='See more']",
            "button[aria-label*='Read more']",
            "button[aria-label*='show more']",
            "button[data-testid='expandable-text-button']",
        ]

        clicks = 0
        for _ in range(max_clicks):
            clicked = False
            for sel in selectors:
                try:
                    for btn in root.query_selector_all(sel):
                        if clicks >= max_clicks:
                            return clicks
                        if not btn or not btn.is_visible():
                            continue
                        try:
                            btn.click(timeout=1500)
                            time.sleep(0.16)
                            clicks += 1
                            clicked = True
                        except Exception:
                            continue
                except Exception:
                    continue

            try:
                for btn in root.query_selector_all("button, span, a"):
                    if clicks >= max_clicks:
                        return clicks
                    if not btn or not btn.is_visible():
                        continue
                    text = (btn.inner_text() or "").strip()
                    if not re.search(r"(see|read|show)\s+more|\.\.\.\s*more|…\s*more", text, re.I):
                        continue
                    try:
                        btn.click(timeout=1500)
                        time.sleep(0.16)
                        clicks += 1
                        clicked = True
                    except Exception:
                        continue
            except Exception:
                pass

            if not clicked:
                break
        return clicks

    def _expand_see_more_on_page(self, max_clicks: int = 40) -> int:
        """Click visible 'see more' / 'read more' controls (feed + search)."""
        clicks = 0
        selectors = [
            "button.feed-shared-inline-show-more-text__see-more--full-width",
            "button.feed-shared-inline-show-more-text__see-more",
            "span.feed-shared-inline-show-more-text__see-more",
            ".feed-shared-inline-show-more-text__see-more-less-toggle",
            "button[aria-label*='See more']",
            "button[aria-label*='Read more']",
            "button[aria-label*='show more']",
            "button[data-testid='expandable-text-button']",
        ]
        for fr in self._iter_scrape_frames():
            for sel in selectors:
                for btn in fr.query_selector_all(sel):
                    if clicks >= max_clicks:
                        return clicks
                    try:
                        if btn.is_visible():
                            btn.click(timeout=1200)
                            clicks += 1
                            time.sleep(0.08)
                    except Exception:
                        pass
        for pattern in (r"see\s+more", r"read\s+more", r"show\s+more"):
            try:
                loc = self.page.get_by_role("button", name=re.compile(pattern, re.I))
                n = loc.count()
                for i in range(min(n, 12)):
                    if clicks >= max_clicks:
                        return clicks
                    try:
                        loc.nth(i).click(timeout=900)
                        clicks += 1
                        time.sleep(0.08)
                    except Exception:
                        pass
            except Exception:
                pass
        return clicks

    def _article_primary_text(self, article) -> str:
        """Post body selectors change often; try several before using the whole card text."""
        self._expand_see_more_in_card(article)
        selectors = [
            ".feed-shared-text",
            ".feed-shared-text__text-view",
            ".feed-shared-update-v2__description",
            ".update-components-text",
            ".feed-shared-inline-show-more-text",
            ".update-components-update__text",
            ".search-result__snippets",
            ".update-components-actor__description",
            "[data-test-post-container] .break-words",
            "span.break-words",
        ]
        best = ""
        for sel in selectors:
            try:
                el = article.query_selector(sel)
                if el:
                    t = (el.inner_text() or "").strip()
                    if len(t) > len(best):
                        best = t
            except Exception:
                continue
        if len(best) < 30 or any(token in best for token in ("… more", "... more", "see more", "read more", "show more")):
            self._expand_see_more_in_card(article, max_clicks=4)
            for sel in selectors:
                try:
                    el = article.query_selector(sel)
                    if el:
                        t = (el.inner_text() or "").strip()
                        if len(t) > len(best):
                            best = t
                except Exception:
                    continue
            try:
                t = (article.inner_text() or "").strip()
                if len(t) > len(best):
                    best = t
            except Exception:
                pass
        return best

    @staticmethod
    def _absolute_url(href: str) -> str:
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            return ""
        href = href.strip()
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return "https://www.linkedin.com" + href
        return href

    @staticmethod
    def _dedupe_preserve(seq: List[str]) -> List[str]:
        seen, out = set(), []
        for x in seq:
            if x and x not in seen:
                seen.add(x)
                out.append(x)
        return out

    def _extract_anchor_rows_from_article(self, article) -> List[Dict[str, str]]:
        try:
            rows = article.evaluate(
                """el => {
                    const out = [];
                    const seen = new Set();
                    el.querySelectorAll('a[href]').forEach(a => {
                        const href = a.getAttribute('href') || '';
                        if (!href || href === '#' || href.startsWith('javascript:')) return;
                        if (seen.has(href)) return;
                        seen.add(href);
                        const text = (a.innerText || '').trim().slice(0, 240);
                        out.push({ href, text });
                    });
                    return out;
                }"""
            )
            return list(rows or [])
        except Exception:
            return []

    def _article_activity_urn(self, article) -> str:
        try:
            u = article.evaluate(
                """el => {
                    const attrs = ['data-urn', 'data-id', 'data-activity-urn'];
                    for (const a of attrs) {
                        const v = el.getAttribute(a);
                        if (v && (v.includes('urn:') || v.includes('activity:'))) return v;
                    }
                    for (let i = 0; i < el.attributes.length; i++) {
                        const n = el.attributes[i].name;
                        const v = el.attributes[i].value || '';
                        if (v && (n.includes('urn') || n.includes('activity')) && v.length > 8)
                            return v;
                    }
                    return '';
                }"""
            )
            if u and isinstance(u, str):
                u = (u or "").strip()
                if u:
                    return u
        except Exception:
            pass

        try:
            for a in article.query_selector_all('a[href]'):
                href = a.get_attribute('href') or ''
                if not href:
                    continue
                aid = self._activity_id_from_href(href)
                if aid:
                    if aid.startswith('ugc:'):
                        return f'urn:li:{aid}'
                    return f'urn:li:activity:{aid}'
        except Exception:
            pass

        return ""

    def _hashtags_in_text(self, text: str) -> List[str]:
        found = re.findall(r"#[A-Za-z0-9_]+", text or "")
        return self._dedupe_preserve(found)

    def _build_post_record(self, article, source: str, post_text: str) -> Dict[str, Any]:
        post_text = (post_text or "").strip()
        author_name = ""
        author_title = ""
        post_url = ""
        date_posted = ""
        likes_count = 0

        author_elem = article.query_selector(".feed-shared-actor__name")
        if author_elem:
            author_name = author_elem.inner_text() or ""

        author_title_elem = article.query_selector(".feed-shared-actor__sub-description")
        if author_title_elem:
            author_title = author_title_elem.inner_text() or ""

        link_elem = article.query_selector(".feed-shared-actor__sub-link")
        if link_elem:
            post_url = self._absolute_url(link_elem.get_attribute("href") or "")

        time_elem = article.query_selector("time")
        if time_elem:
            date_posted = time_elem.get_attribute("datetime") or ""

        likes_elem = article.query_selector(
            ".feed-shared-social-proofs__social-count-of-non-impressions"
        )
        if likes_elem:
            try:
                likes_text = likes_elem.inner_text() or ""
                likes_count = int(likes_text.split()[0].replace(",", ""))
            except Exception:
                likes_count = 0

        raw_rows = self._extract_anchor_rows_from_article(article)
        links: List[Dict[str, str]] = []
        seen_h = set()
        for row in raw_rows:
            h = self._absolute_url(row.get("href") or "")
            if not h or h in seen_h:
                continue
            seen_h.add(h)
            links.append({"href": h, "text": (row.get("text") or "").strip()})

        if not post_url:
            for row in links:
                href = row["href"]
                low = href.lower()
                if any(k in low for k in ["/feed/update/", "/posts/", "activity%3a", "urn:li:activity", "/activity/"]):
                    post_url = href
                    break

        if not post_url:
            for row in links:
                href = row["href"]
                low = href.lower()
                if "linkedin.com/feed/" in low or "linkedin.com/posts/" in low:
                    post_url = href
                    break

        external_urls: List[str] = []
        linkedin_job_urls: List[str] = []
        linkedin_profile_urls: List[str] = []
        for L in links:
            h = L["href"]
            lu = h.lower()
            if "linkedin.com" in lu:
                if "/jobs/" in lu or "/job/" in lu:
                    linkedin_job_urls.append(h)
                if "/in/" in lu:
                    linkedin_profile_urls.append(h)
            elif h.startswith("http://") or h.startswith("https://"):
                external_urls.append(h)

        activity_urn = self._article_activity_urn(article)

        return {
            "post_text": post_text,
            "author_name": author_name.strip(),
            "author_title": author_title.strip(),
            "post_url": post_url,
            "date_posted": date_posted,
            "likes_count": likes_count,
            "source": source,
            "links": links,
            "external_urls": self._dedupe_preserve(external_urls),
            "linkedin_job_urls": self._dedupe_preserve(linkedin_job_urls),
            "linkedin_profile_urls": self._dedupe_preserve(linkedin_profile_urls),
            "hashtags_in_text": self._hashtags_in_text(post_text),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "activity_urn": activity_urn,
        }

    @staticmethod
    def _post_dedupe_key(post: Dict[str, Any]) -> str:
        u = (post.get("activity_urn") or "").strip()
        if u:
            return f"urn:{u}"
        return f"{post.get('author_name', '')}|{(post.get('post_text') or '')[:220]}"

    def scrape_feed(self) -> Generator[Dict[str, Any], None, None]:
        """Scrape posts from LinkedIn feed."""
        print("[SCRAPER] Starting feed scrape...")

        try:
            # region agent log
            _agent_dbg(
                "scraper.py:scrape_feed:try_enter",
                "feed_scrape_try_start",
                {},
                "H5",
            )
            # endregion
            self.page.goto("https://www.linkedin.com/feed/", timeout=30000)
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.wait_for_load_state("load", timeout=20000)
            except Exception:
                pass
            try:
                self.page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            hydrated = self._wait_feed_shell_hydrated(60000)
            if not hydrated:
                print(
                    "[SCRAPER] Warning: feed UI did not hydrate (no feed/scaffold in DOM). "
                    "If the window looks blank, try completing any LinkedIn prompt in the browser."
                )
            # region agent log
            _agent_dbg(
                "scraper.py:scrape_feed:after_goto",
                "feed_after_nav",
                {
                    "page_url_tail": (self.page.url or "")[-140:],
                    "hydrated": hydrated,
                    "shell_probe": self._linkedin_shell_probe(),
                },
                "H5",
            )
            # endregion
            card_wait = (
                "[data-test-post-container], div.feed-shared-update-v2, "
                "article.feed-shared-update-v2, "
                "li.reusable-search__result-container, main article, "
                "a[href*=\"urn:li:activity\"], a[href*=\"/feed/update/\"], "
                "[data-view-name=\"search-entity-result-universal-template\"], "
                "div[data-chameleon-result-urn]"
            )
            try:
                self.page.wait_for_selector(card_wait, timeout=30000)
            except Exception:
                print("[SCRAPER] Warning: no post cards yet; continuing anyway")
            time.sleep(2.0)
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass
            self._expand_see_more_on_page()
            time.sleep(0.8)
            self._random_delay()

            use_keyword_gate = not config.FEED_AI_TRIAGE_RAW
            # region agent log
            _agent_dbg(
                "scraper.py:scrape_feed:after_expand",
                "feed_ready",
                {
                    "page_url_tail": (self.page.url or "")[-120:],
                    "FEED_AI_TRIAGE_RAW": config.FEED_AI_TRIAGE_RAW,
                    "use_keyword_gate": use_keyword_gate,
                    "selector_counts": self._dom_selector_counts(),
                    "pierce_probe": self._query_vs_locator_probe(),
                    "dom_probe_main": self._linkedin_dom_probe_main(),
                    "shell_probe": self._linkedin_shell_probe(),
                },
                "H1_H2_H3_H5",
            )
            # endregion

            keywords = [
                "hiring", "we're hiring", "we are hiring", "looking for", "open role",
                "job opening", "opportunity", "#hiring", "#jobopening",
                "#nowhiring", "#opportunity"
            ]

            max_feed_articles = 0
            sum_feed_kw_skip = 0
            sum_feed_empty = 0

            for scroll_num in range(1, config.FEED_SCROLL_COUNT + 1):
                print(f"[SCRAPER] Feed pass {scroll_num}/{config.FEED_SCROLL_COUNT}")
                if scroll_num > 1:
                    self._scroll_linkedin_main()
                    self._wheel_scroll_fallback()
                    time.sleep(config.FEED_SCROLL_DELAY)
                    self._random_delay()
                    self._expand_see_more_on_page(18)

                try:
                    articles = self._list_post_cards()
                    print(f"  → {len(articles)} post card(s) in DOM")
                    print(
                        f"[SCRAPER] DEBUG: total post cards on page "
                        f"(feed pass {scroll_num}/{config.FEED_SCROLL_COUNT}): {len(articles)}"
                    )

                    n_empty = 0
                    n_kw_skip = 0
                    n_added = 0

                    for article in articles:
                        try:
                            post_text = self._article_primary_text(article)
                            if not post_text.strip():
                                n_empty += 1
                                continue
                            post_lower = post_text.lower()
                            if use_keyword_gate:
                                if not any(
                                    kw.lower() in post_lower for kw in keywords
                                ):
                                    n_kw_skip += 1
                                    continue

                            post_data = self._build_post_record(
                                article, "feed", post_text
                            )
                            yield post_data
                            n_added += 1
                            label = (
                                "hiring signal"
                                if use_keyword_gate
                                else "feed (AI triage)"
                            )
                            print(
                                f"  → Found {label} from {post_data['author_name']}"
                            )

                        except Exception:
                            continue

                    # region agent log
                    sample_len = 0
                    if articles:
                        try:
                            t0 = self._article_primary_text(articles[0])
                            sample_len = len((t0 or "").strip())
                        except Exception:
                            sample_len = -1
                    _agent_dbg(
                        "scraper.py:scrape_feed:scroll_pass",
                        "feed_pass_stats",
                        {
                            "scroll_num": scroll_num,
                            "articles": len(articles),
                            "n_empty_text": n_empty,
                            "n_keyword_skip": n_kw_skip,
                            "n_added": n_added,
                            "first_card_text_len": sample_len,
                        },
                        "H1_H3",
                    )
                    # endregion

                    max_feed_articles = max(max_feed_articles, len(articles))
                    sum_feed_kw_skip += n_kw_skip
                    sum_feed_empty += n_empty

                except Exception as e:
                    print(f"  → Error getting articles: {e}")

        except Exception as e:
            print(f"[SCRAPER] ERROR in feed scrape: {e}")
            self._save_screenshot("feed_error")

    def _scrape_content_search(
        self,
        keywords_raw: str,
        *,
        source_tag: str,
        log_label: str,
        screenshot_slug: str,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        LinkedIn /search/results/content/ — same UI for #hashtags and plain keywords.
        keywords_raw is encoded for the `keywords=` query param (e.g. '#hiring' or 'Flutter developer').
        """
        kw_enc = quote(keywords_raw, safe="")
        try:
            url = (
                "https://www.linkedin.com/search/results/content/"
                f"?keywords={kw_enc}&origin=FACETED_SEARCH"
                f"{config.content_search_extra_query()}"
            )
            print(f"[SCRAPER] Content search [{log_label}] → {url}")

            self.page.goto(url, timeout=30000)
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.wait_for_load_state("load", timeout=20000)
            except Exception:
                pass
            try:
                self.page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            self._wait_feed_shell_hydrated(60000)
            card_wait = (
                "[data-test-post-container], div.feed-shared-update-v2, "
                "article.feed-shared-update-v2, "
                "li.reusable-search__result-container, main .search-results-container article, "
                "a[href*=\"urn:li:activity\"], a[href*=\"/feed/update/\"], "
                "[data-view-name=\"search-entity-result-universal-template\"], "
                "div[data-chameleon-result-urn], "
                "[role='listitem'], [componentkey*='FeedType_FLAGSHIP_SEARCH']"
            )
            try:
                self.page.wait_for_selector(card_wait, timeout=30000)
            except Exception:
                print(f"[SCRAPER] Warning: [{log_label}] — no cards in time; continuing")
            time.sleep(2.0)
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass
            self._expand_see_more_on_page()
            time.sleep(0.8)
            self._random_delay()

            # region agent log
            _agent_dbg(
                "scraper.py:_scrape_content_search:after_expand",
                "content_search_ready",
                {
                    "log_label": log_label[:120],
                    "keywords_raw_len": len(keywords_raw),
                    "page_url_tail": (self.page.url or "")[-140:],
                    "content_type_filter_len": len(
                        (config.SEARCH_FILTER_CONTENT_TYPE or "").strip()
                    ),
                    "selector_counts": self._dom_selector_counts(),
                    "pierce_probe": self._query_vs_locator_probe(),
                    "shell_probe": self._linkedin_shell_probe(),
                },
                "H1_H2_H3_H4_H5",
            )
            # endregion

            count = 0
            cap = config.POSTS_PER_HASHTAG

            for pass_num in range(1, config.HASHTAG_SCROLL_COUNT + 1):
                if pass_num > 1:
                    self._scroll_linkedin_main()
                    self._wheel_scroll_fallback()
                    time.sleep(config.FEED_SCROLL_DELAY)
                    self._random_delay()
                    self._expand_see_more_on_page(18)

                articles = self._list_post_cards()
                print(
                    f"  → [{log_label}] pass {pass_num}/"
                    f"{config.HASHTAG_SCROLL_COUNT}: {len(articles)} card(s)"
                )
                print(
                    f"[SCRAPER] DEBUG: total post cards on page "
                    f"([{log_label}] pass {pass_num}/{config.HASHTAG_SCROLL_COUNT}): "
                    f"{len(articles)}"
                )

                n_empty = 0
                for article in articles:
                    if count >= cap:
                        break
                    try:
                        post_text = self._article_primary_text(article)
                        if not post_text.strip():
                            n_empty += 1
                            continue

                        post_data = self._build_post_record(
                            article, source_tag, post_text
                        )
                        yield post_data
                        count += 1
                        print(f"  → Found post #{count}")

                    except Exception as e:
                        print(f"  → Error parsing article: {e}")
                        continue

                # region agent log
                _agent_dbg(
                    "scraper.py:_scrape_content_search:pass",
                    "content_search_pass_stats",
                    {
                        "log_label": log_label[:120],
                        "pass_num": pass_num,
                        "articles": len(articles),
                        "n_empty_text": n_empty,
                        "count_so_far": count,
                    },
                    "H3_H4",
                )
                # endregion

                if count >= cap:
                    break

            print(f"[SCRAPER] [{log_label}] search complete. Found {count} posts")

        except Exception as e:
            print(f"[SCRAPER] ERROR in [{log_label}] search: {e}")
            safe_slug = re.sub(r"[^\w\-]+", "_", screenshot_slug)[:80]
            self._save_screenshot(f"search_{safe_slug}_error")

    def scrape_hashtag_search(self, hashtag: str) -> Generator[Dict[str, Any], None, None]:
        """Scrape posts for a specific hashtag (#tag)."""
        print(f"[SCRAPER] Searching hashtag: #{hashtag}")
        yield from self._scrape_content_search(
            f"#{hashtag}",
            source_tag=f"search #{hashtag}",
            log_label=f"#{hashtag}",
            screenshot_slug=f"hashtag_{hashtag}",
        )

    def scrape_keyword_search(self, query: str) -> Generator[Dict[str, Any], None, None]:
        """Scrape posts for a plain keyword phrase (e.g. 'Flutter developer')."""
        q = (query or "").strip()
        if not q:
            return
        print(f"[SCRAPER] Keyword search: {q!r}")
        slug = q.replace(" ", "_")[:40]
        yield from self._scrape_content_search(
            q,
            source_tag=f"search kw:{q}",
            log_label=q[:80],
            screenshot_slug=f"kw_{slug}",
        )

    def _shutdown_browser(self):
        """Close browser context and stop Playwright driver (always pair these)."""
        if self.browser is not None:
            try:
                self.browser.close()
            except Exception as e:
                print(f"[SCRAPER] Error closing browser: {e}")
            finally:
                self.browser = None
                self.context = None
                self.page = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception as e:
                print(f"[SCRAPER] Error stopping Playwright: {e}")
            finally:
                self._playwright = None

    def _dedupe_posts_buffer(self) -> None:
        """Deduplicate self.posts by hash of first 200 chars of post_text."""
        unique_posts: List[Dict[str, Any]] = []
        seen_texts = set()
        for post in self.posts:
            text_key = (post.get("post_text") or "")[:200]
            text_hash = hash(text_key)
            if text_hash not in seen_texts:
                seen_texts.add(text_hash)
                unique_posts.append(post)
        self.posts = unique_posts

    def run(self) -> Generator[Dict[str, Any], None, None]:
        """Run full scraping process."""
        print("\n" + "=" * 50)
        print("LINKEDIN JOB SCRAPER")
        print("=" * 50)
        scrape_interrupted = False
        try:
            # region agent log
            _agent_dbg(
                "scraper.py:run:enter",
                "run_start",
                {"debug_log": str(_AGENT_DBG_LOG)},
                "H0",
            )
            # endregion
            print(f"[SCRAPER] Session debug log: {_AGENT_DBG_LOG}")
            self.launch_browser()
            self.login()

            url = (self.page.url or "").lower()
            if "linkedin.com/login" in url or "checkpoint" in url:
                self._save_screenshot("session_blocked")
                raise RuntimeError(
                    "LinkedIn session is blocked or still on login/checkpoint. "
                    "Finish sign-in or verification in the browser, then run again."
                )

            try:
                print("\n--- Step 1: Scraping Feed ---")
                # self.posts.extend(self.scrape_feed())  # Skipped to avoid feed post issues

                print("\n--- Step 2: Scraping Hashtags ---")
                for hashtag in config.HASHTAGS:
                    yield from self.scrape_hashtag_search(hashtag)
                    self._random_delay()

                print("\n--- Step 3: Keyword / phrase searches (content) ---")
                for query in config.CONTENT_SEARCH_QUERIES:
                    q = (query or "").strip()
                    if not q:
                        continue
                    yield from self.scrape_keyword_search(q)
                    self._random_delay()
            except KeyboardInterrupt:
                print(
                    "\n[SCRAPER] Ctrl+C — stopping scrape. "
                    "Collected raw post(s) so far; continuing."
                )
                scrape_interrupted = True
            except Exception as e:
                print(f"\n[SCRAPER] Scrape error ({type(e).__name__}): {e}")
                print(
                    "Continuing with post(s) collected so far …"
                )
                scrape_interrupted = True

        finally:
            self._shutdown_browser()