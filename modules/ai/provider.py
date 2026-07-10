from abc import ABC, abstractmethod


class ProviderRateLimitError(Exception):
    pass


class ProviderPayloadTooLargeError(Exception):
    pass


class ProviderTimeoutError(Exception):
    pass


class ProviderConnectionError(Exception):
    pass


class AIProvider(ABC):
    @abstractmethod
    def triage(self, post_json: str) -> str: ...

    @abstractmethod
    def enrich(self, post_json: str) -> str: ...

    @abstractmethod
    def current_model(self) -> str: ...

    @abstractmethod
    def max_attempts(self) -> int: ...

    @abstractmethod
    def advance(self) -> None: ...


def make_provider(profile: str) -> AIProvider:
    import config
    if config.AI_PROVIDER == "claude":
        from modules.ai.claude_provider import ClaudeProvider
        return ClaudeProvider(profile)
    from modules.ai.openai_provider import OpenAIProvider
    return OpenAIProvider(profile)
