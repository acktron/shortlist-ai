class AIProviderError(RuntimeError):
    """Base error for failures that should be reported as AI service failures."""


class AIUnavailableError(AIProviderError):
    """The configured AI provider could not complete a request."""
