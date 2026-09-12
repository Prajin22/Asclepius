"""Structured AI failure states. A failure never produces a fabricated result."""


class AIError(Exception):
    code = "ai_error"

    def __init__(self, message: str = "", *, provider: str | None = None):
        super().__init__(message or self.code)
        self.message = message or self.code
        self.provider = provider


class AICredentialsMissing(AIError):
    code = "ai_credentials_missing"


class AIConfigurationError(AIError):
    code = "ai_configuration_error"


class AITimeout(AIError):
    code = "ai_timeout"


class AIProviderUnavailable(AIError):
    """Network failure, 5xx, or rate limit."""

    code = "ai_provider_unavailable"


class AIMalformedOutput(AIError):
    """The provider returned something that does not match the schema."""

    code = "ai_malformed_output"


class AICapabilityUnsupported(AIError):
    """The configured provider cannot perform this operation (e.g. read images)."""

    code = "ai_capability_unsupported"


class AICircuitOpen(AIError):
    """Recent failures tripped the breaker; we are not calling the provider."""

    code = "ai_circuit_open"
