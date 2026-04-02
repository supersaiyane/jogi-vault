"""CSRF protection middleware for Jogi Vault."""
from __future__ import annotations

import secrets

from flask import session, request
from markupsafe import Markup


def _csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(32)
    return session["_csrf"]


def _csrf_input() -> str:
    return '<input type="hidden" name="_csrf" value="{}">'.format(_csrf_token())


def init_csrf(app):
    """Register CSRF before_request validation and context processor."""

    @app.before_request
    def _validate_csrf():
        """Reject POST requests without valid CSRF token (except API routes)."""
        if request.method != "POST":
            return
        if request.path.startswith("/api/"):
            return
        token = request.form.get("_csrf", "")
        expected = session.get("_csrf", "")
        if not expected or not token or not secrets.compare_digest(token, expected):
            from vault.helpers import error_page
            return error_page(403, "Invalid request",
                "The form submission could not be verified. "
                "Please go back and try again.")

    @app.context_processor
    def inject_csrf():
        def csrf_field():
            return Markup(_csrf_input())
        return {"csrf_field": csrf_field}
