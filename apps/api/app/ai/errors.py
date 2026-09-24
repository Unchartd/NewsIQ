class AIGatewayError(Exception):
    """Base exception for all AI Gateway operations."""

    pass


class ProviderUnavailableError(AIGatewayError):
    """Raised when a configured provider is unreachable, returns 5xx, or is offline."""

    pass


class RateLimitError(AIGatewayError):
    """Raised when a provider returns a 429 Rate Limit or Quota Exceeded error."""

    pass


class ValidationError(AIGatewayError):
    """Raised when the LLM response fails validation against the Pydantic schema."""

    pass


class TimeoutError(AIGatewayError):
    """Raised when the request to the provider times out."""

    pass


class AuthenticationError(AIGatewayError):
    """Raised when the provider rejects the API key."""

    pass


class AllProvidersFailedError(AIGatewayError):
    """Raised when every route in a fallback chain failed.

    ``provider_outage`` separates the two reasons a whole chain fails, which
    callers must handle differently:

    * True — no model produced an answer. Every attempt was a rate limit,
      timeout, outage or rejected key, or every route was skipped as
      exhausted. Retrying the same input later will likely succeed; the
      pipeline should back off rather than burn through its backlog.
    * False — at least one model answered but its output failed validation.
      That points at this input or prompt, not at the providers.

    Subclasses AIGatewayError so every existing ``except AIGatewayError``
    keeps working unchanged.
    """

    def __init__(self, message: str, *, provider_outage: bool):
        super().__init__(message)
        self.provider_outage = provider_outage
