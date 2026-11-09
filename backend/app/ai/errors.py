class AIProviderError(RuntimeError):
    """Base error for failures that should be reported as AI service failures."""


class AIUnavailableError(AIProviderError):
    """The configured AI provider could not complete a request."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
