from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

import config
from modules.ai.provider import (
    AIProvider,
    ProviderConnectionError,
    ProviderPayloadTooLargeError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)


class OpenAIProvider(AIProvider):
    def __init__(self, profile: str):
        self._profile = profile
        self._model_idx = 0
        self._models = config.OPENAI_MODELS
        self._client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            timeout=config.AI_REQUEST_TIMEOUT,
        )

    def current_model(self) -> str:
        return self._models[self._model_idx % len(self._models)]

    def max_attempts(self) -> int:
        return len(self._models)

    def advance(self) -> None:
        self._model_idx += 1

    def _chat_json(self, *, system: str, user: str, max_tokens: int, temperature: float) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self.current_model(),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw = response.choices[0].message.content
            return (raw or "").strip()
        except RateLimitError as e:
            raise ProviderRateLimitError(e) from e
        except APIStatusError as e:
            if e.status_code in (400, 413):
                raise ProviderPayloadTooLargeError(e) from e
            raise
        except APITimeoutError as e:
            raise ProviderTimeoutError(e) from e
        except APIConnectionError as e:
            raise ProviderConnectionError(e) from e

    def triage(self, post_json: str) -> str:
        profile_head = (self._profile or "")[:2000]
        user = config.TRIAGE_USER_TEMPLATE.format(
            profile_head=profile_head,
            post_json=post_json,
        )
        return self._chat_json(
            system=config.TRIAGE_SYSTEM_PROMPT,
            user=user,
            max_tokens=config.AI_MAX_TOKENS_TRIAGE,
            temperature=0.1,
        )

    def enrich(self, post_json: str) -> str:
        user = config.USER_ENRICHMENT_PROMPT_TEMPLATE.format(
            profile=self._profile,
            post_json=post_json,
        )
        return self._chat_json(
            system=config.ENRICHMENT_SYSTEM_PROMPT,
            user=user,
            max_tokens=config.AI_MAX_TOKENS_ENRICH,
            temperature=0.3,
        )
