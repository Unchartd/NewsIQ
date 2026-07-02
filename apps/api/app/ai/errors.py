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
