"""
Jogi Vault — Flask app factory.
"""
from __future__ import annotations

import os
import secrets as _secrets

from flask import Flask, session
from markupsafe import Markup

from src.vault import Vault

# ── APScheduler ───────────────────────────────────────────────────────────────
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.start()
    SCHEDULER_AVAILABLE = True
except ImportError:
    _scheduler = None
    SCHEDULER_AVAILABLE = False


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.secret_key = _secrets.token_hex(32)

    # Auto-unlock from environment
    _try_env_unlock(app)

    # Register middleware
    from vault.middleware import init_csrf
    init_csrf(app)

    # Register error handlers
    _register_error_handlers(app)

    # Register context processors
    _register_context_processors(app)

    # Register routes
    from vault.routes import register_routes
    register_routes(app)

    return app


def _try_env_unlock(app):
    """Auto-unlock vault from VAULT_PASSWORD env var (needed for API without UI login)."""
    pwd = os.environ.get("VAULT_PASSWORD", "").strip()
    if pwd and Vault.is_initialised():
        try:
            Vault(password=pwd, _skip_totp=True)
            app.config["_backup_pwd"] = pwd
        except Exception:
            pass


def _register_error_handlers(app):
    from vault.helpers import error_page

    @app.errorhandler(404)
    def not_found(e):
        return error_page(
            404,
            "Page not found",
            "This page doesn&rsquo;t exist in the vault.<br>"
            "Maybe the URL changed, or you followed a stale link."
        )

    @app.errorhandler(500)
    def server_error(e):
        return error_page(
            500,
            "Something went wrong",
            "An unexpected error occurred inside the vault.<br>"
            "Your data is safe &mdash; this is just a server hiccup."
        )

    @app.errorhandler(403)
    def forbidden(e):
        return error_page(
            403,
            "Access denied",
            "You don&rsquo;t have permission to access this page.<br>"
            "Please log in first."
        )


def _register_context_processors(app):
    @app.context_processor
    def inject_helpers():
        from vault.helpers import current_ns as _current_ns

        def pop_msgs():
            msgs = session.pop("_msgs", [])
            return Markup("".join(
                '<div class="flash {}">{}</div>'.format(c, t) for c, t in msgs
            ))

        return {
            "pop_msgs": pop_msgs,
            "current_ns": _current_ns(),
            "all_ns": Vault.list_namespaces(),
            "active_tab": "",
        }

    @app.context_processor
    def inject_active_tab():
        """Set active_tab based on the current request path."""
        from flask import request
        path = request.path
        if path.startswith("/backup"):
            tab = "backup"
        elif path.startswith("/api-settings"):
            tab = "api"
        elif path.startswith("/vault"):
            tab = "secrets"
        else:
            tab = ""
        return {"active_tab": tab}


# ── Scheduler ────────────────────────────────────────────────────────────────

# Module-level storage for the backup password (used by scheduler thread)
_backup_pwd_store = {"pwd": None}


def start_backup_scheduler(password: str, frequency_hours: int) -> None:
    """(Re)schedule the auto-backup job."""
    if not SCHEDULER_AVAILABLE or _scheduler is None:
        return
    from flask import current_app
    current_app.config["_backup_pwd"] = password
    _backup_pwd_store["pwd"] = password
    _scheduler.add_job(
        _run_scheduled_backup,
        trigger=IntervalTrigger(hours=frequency_hours),
        id="vault_backup",
        replace_existing=True,
    )


def _run_scheduled_backup() -> None:
    """Runs in background thread — no request context available."""
    pwd = _backup_pwd_store.get("pwd")
    if not pwd:
        return
    try:
        from vault.services.backup import BackupManager
        vault = Vault(password=pwd, _skip_totp=True)
        bm    = BackupManager(vault)
        cfg   = bm.get_config()
        if cfg["enabled"] and cfg["gdrive_connected"]:
            name = bm.backup_now()
            import logging
            logging.getLogger("vault").info("Scheduled backup: %s", name)
    except Exception as exc:
        import logging
        logging.getLogger("vault").error("Scheduled backup failed: %s", exc)
