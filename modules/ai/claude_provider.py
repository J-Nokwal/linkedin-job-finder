import asyncio
import os

import config
from modules.ai.provider import (
    AIProvider,
    ProviderConnectionError,
    ProviderPayloadTooLargeError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)


class ClaudeProvider(AIProvider):
    """
    Two auth modes selected automatically at construction:

    1. ANTHROPIC_API_KEY set  → anthropic SDK, direct API calls, prompt caching enabled.
    2. ANTHROPIC_API_KEY empty → claude_agent_sdk, reuses ~/.claude/ (Claude Code subscription).
    """

    def __init__(self, profile: str):
        self._profile = profile
        self._model = config.CLAUDE_MODEL or None
        self._use_api_key = bool(config.ANTHROPIC_API_KEY)

        if self._use_api_key:
            import anthropic
            self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            profile_head = (profile or "")[:2000]
            # Profile block cached server-side after the first call.
            self._triage_system = [
                {"type": "text", "text": config.TRIAGE_SYSTEM_PROMPT},
                {
                    "type": "text",
                    "text": f"CANDIDATE PROFILE (first 2000 chars):\n{profile_head}",
                    "cache_control": {"type": "ephemeral"},
                },
            ]
            self._enrich_system = [
                {"type": "text", "text": config.ENRICHMENT_SYSTEM_PROMPT},
                {
                    "type": "text",
                    "text": f"CANDIDATE PROFILE:\n{profile}",
                    "cache_control": {"type": "ephemeral"},
                },
            ]
        else:
            # claude_agent_sdk path — no API key needed, uses ~/.claude/ auth.
            try:
                import claude_agent_sdk  # noqa: F401
            except ImportError:
                raise ImportError(
                    "claude_agent_sdk is not installed. "
                    "Install it with: pip install claude-agent-sdk  "
                    "Or set ANTHROPIC_API_KEY to use the direct API instead."
                ) from None

    # ------------------------------------------------------------------
    # anthropic SDK path (with prompt caching)
    # ------------------------------------------------------------------

    def _call_api(self, system: list, user_text: str, max_tokens: int, temperature: float) -> str:
        import anthropic
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user_text}],
                betas=["prompt-caching-2024-07-31"],
            )
            return resp.content[0].text
        except anthropic.RateLimitError as e:
            raise ProviderRateLimitError(e) from e
        except anthropic.APIStatusError as e:
            if e.status_code in (400, 413):
                raise ProviderPayloadTooLargeError(e) from e
            raise
        except anthropic.APITimeoutError as e:
            raise ProviderTimeoutError(e) from e
        except anthropic.APIConnectionError as e:
            raise ProviderConnectionError(e) from e

    # ------------------------------------------------------------------
    # claude_agent_sdk path (Claude Code subscription, no API key)
    # ------------------------------------------------------------------

    async def _async_call_sdk(self, prompt: str) -> str:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        options = ClaudeAgentOptions(
            permission_mode="dontAsk",
            allowed_tools=[],
            model=self._model,
        )

        result_msg: ResultMessage | None = None
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage):
                result_msg = msg

        if result_msg is None:
            raise RuntimeError("claude_agent_sdk: no ResultMessage received")
        if result_msg.is_error:
            errors = "; ".join(result_msg.errors or ["unknown error"])
            raise RuntimeError(f"claude_agent_sdk call failed: {errors}")

        return result_msg.result or ""

    def _call_sdk(self, prompt: str) -> str:
        return asyncio.run(self._async_call_sdk(prompt))

    # ------------------------------------------------------------------
    # AIProvider interface
    # ------------------------------------------------------------------

    def triage(self, post_json: str) -> str:
        if self._use_api_key:
            return self._call_api(
                self._triage_system, post_json, config.AI_MAX_TOKENS_TRIAGE, 0.1
            )
        profile_head = (self._profile or "")[:2000]
        prompt = (
            f"{config.TRIAGE_SYSTEM_PROMPT}\n\n"
            f"CANDIDATE PROFILE (first 2000 chars):\n{profile_head}\n\n"
            f"POST_JSON:\n{post_json}"
        )
        return self._call_sdk(prompt)

    def enrich(self, post_json: str) -> str:
        if self._use_api_key:
            return self._call_api(
                self._enrich_system, post_json, config.AI_MAX_TOKENS_ENRICH, 0.3
            )
        prompt = (
            f"{config.ENRICHMENT_SYSTEM_PROMPT}\n\n"
            + config.USER_ENRICHMENT_PROMPT_TEMPLATE.format(
                profile=self._profile, post_json=post_json
            )
        )
        return self._call_sdk(prompt)

    def current_model(self) -> str:
        return self._model or "claude (default)"

    def max_attempts(self) -> int:
        return 1

    def advance(self) -> None:
        pass
