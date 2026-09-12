"""Domain errors. Translated to HTTP in exactly one place (app.main)."""


class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(self, message: str = "", *, code: str | None = None):
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__
        if code:
            self.code = code


class NotFound(DomainError):
    status_code = 404
    code = "not_found"


class Forbidden(DomainError):
    status_code = 403
    code = "forbidden"


class Conflict(DomainError):
    status_code = 409
    code = "conflict"


class InvalidInput(DomainError):
    status_code = 422
    code = "invalid_input"


class InvalidTransition(DomainError):
    status_code = 409
    code = "invalid_transition"


class AuthenticationFailed(DomainError):
    status_code = 401
    code = "authentication_failed"


class AIConsentRequired(DomainError):
    """No AI processing happens until the patient has explicitly opted in."""

    status_code = 403
    code = "ai_consent_required"


class AIUnavailable(DomainError):
    """AI could not run. The original patient information is unaffected."""

    status_code = 503
    code = "ai_unavailable"


class DocumentIntegrityError(DomainError):
    """The stored file no longer matches the bytes that were uploaded."""

    status_code = 409
    code = "document_integrity_failed"


class DocumentUnreadable(DomainError):
    status_code = 422
    code = "document_unreadable"


class AIRateLimited(DomainError):
    """Per-patient AI budget exhausted. Bounds both abuse and provider spend."""

    status_code = 429
    code = "ai_rate_limited"
