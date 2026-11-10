"""Errors raised by the PayPal integration. None of them ever carry credentials or tokens."""


class PayPalError(Exception):
    """Base class."""


class PayPalConfigError(PayPalError):
    """Credentials missing or the mode isn't sandbox."""


class PayPalAuthError(PayPalError):
    """PayPal refused the client id / secret. Nothing else was sent."""


class PayPalUnavailable(PayPalError):
    """The request never reached PayPal (connection refused, DNS, connect timeout). Safe to retry."""


class PayPalTimeout(PayPalError):
    """The request was sent but no answer came back. The outcome is UNKNOWN: reconcile before retrying."""


class PayPalAPIError(PayPalError):
    """PayPal answered with an error status."""

    def __init__(self, status_code: int, name: str, message: str, debug_id: str | None = None, issues: list[str] | None = None):
        detail = f" [{', '.join(issues)}]" if issues else ""
        super().__init__(f"PayPal {status_code} {name}{detail}: {message}")
        self.status_code = status_code
        self.name = name
        self.message = message
        self.debug_id = debug_id
        self.issues = issues or []

    def has_issue(self, issue: str) -> bool:
        return issue in self.issues or self.name == issue
