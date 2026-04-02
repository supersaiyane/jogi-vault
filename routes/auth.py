"""Auth routes: login, logout, setup wizard, emergency key rotation."""
from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from src.vault import (
    Vault, VaultError, TOTPInvalidError,
    TOTPRequiredError, EmergencyKeyUsed,
)
from vault.helpers import (
    login_required, add_msg, uri_to_qr_img_tag,
)
from vault.middleware.session_crypto import _session_encrypt
from vault.middleware.rate_limit import _is_rate_limited, _record_login_attempt

auth_bp = Blueprint("auth", __name__)


# ── Setup wizard ──────────────────────────────────────────────────────────────

@auth_bp.route("/setup/password", methods=["GET", "POST"])
def setup_password():
    if Vault.is_initialised():
        return render_template("vault_exists.html")
    if request.method == "POST":
        pwd1 = request.form.get("pwd1", "").strip()
        pwd2 = request.form.get("pwd2", "").strip()
        if not pwd1:
            flash("Password cannot be empty")
        elif pwd1 != pwd2:
            flash("Passwords do not match")
        else:
            session["setup_pwd"] = pwd1
            return redirect(url_for("auth.setup_totp"))
    return render_template("setup_password.html")


@auth_bp.route("/setup/totp", methods=["GET", "POST"])
def setup_totp():
    if Vault.is_initialised():
        return render_template("vault_exists.html")
    pwd = session.get("setup_pwd")
    if not pwd:
        return redirect(url_for("auth.setup_password"))

    if "setup_uri" not in session:
        vault = Vault(password=pwd, _skip_totp=True)
        session["setup_uri"] = vault.setup_totp()

    uri    = session["setup_uri"]
    qr_img = uri_to_qr_img_tag(uri)
    error  = ""

    if request.method == "POST":
        code  = request.form.get("code", "").strip()
        vault = Vault(password=pwd, _skip_totp=True)
        if vault.verify_totp_code(code):
            session["setup_recovery"]  = vault.init_recovery_key()
            session["setup_emergency"] = vault.generate_emergency_key()
            session.pop("setup_uri", None)
            return redirect(url_for("auth.setup_done"))
        error = "Wrong code — check your authenticator and try again."

    return render_template("setup_totp.html", qr_img=qr_img, uri=uri, error=error)


@auth_bp.route("/setup/done", methods=["GET", "POST"])
def setup_done():
    if Vault.is_initialised() and "setup_recovery" not in session:
        return render_template("vault_exists.html")
    recovery  = session.get("setup_recovery", "")
    emergency = session.get("setup_emergency", "")
    if request.method == "POST":
        for k in ("setup_recovery", "setup_emergency", "setup_pwd"):
            session.pop(k, None)
        add_msg("ok", "Vault ready. Login with your password + authenticator code.")
        return redirect(url_for("auth.login"))
    return render_template("setup_done.html", recovery=recovery, emergency=emergency)


# ── Home ──────────────────────────────────────────────────────────────────────

@auth_bp.route("/")
def home():
    if not Vault.is_initialised():
        return render_template("home.html")
    return redirect(url_for("auth.login"))


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if not Vault.is_initialised():
        return redirect(url_for("auth.home"))
    error = ""
    if request.method == "POST":
        client_ip = request.remote_addr or "unknown"
        if _is_rate_limited(client_ip):
            error = "Too many login attempts. Please wait a few minutes."
        else:
            _record_login_attempt(client_ip)
            pwd  = request.form.get("password", "").strip()
            code = request.form.get("code", "").strip() or None
            try:
                Vault(password=pwd, totp_code=code)
                session["vault_password"] = _session_encrypt(pwd)
                _maybe_start_scheduler(pwd)
                return redirect(url_for("secrets.index"))
            except EmergencyKeyUsed as e:
                session["vault_password"] = _session_encrypt(pwd)
                session["emergency_new"]  = e.new_key
                _maybe_start_scheduler(pwd)
                return redirect(url_for("auth.emergency_rotated"))
            except TOTPInvalidError:
                error = "Wrong authenticator code."
            except TOTPRequiredError:
                error = "This vault requires an authenticator code."
            except VaultError:
                error = "Wrong password."
    return render_template("login.html", error=error)


def _maybe_start_scheduler(password: str) -> None:
    """Start backup scheduler if backup is enabled and Drive is connected."""
    try:
        from vault.services.backup import BackupManager
        from vault.app import start_backup_scheduler
        vault = Vault(password=password, _skip_totp=True)
        bm    = BackupManager(vault)
        cfg   = bm.get_config()
        if cfg["enabled"] and cfg["gdrive_connected"]:
            start_backup_scheduler(password, cfg["frequency_hours"])
    except Exception:
        pass


# ── Logout ────────────────────────────────────────────────────────────────────

@auth_bp.route("/logout")
def logout():
    from flask import current_app
    current_app.config.pop("_backup_pwd", None)
    session.clear()
    return redirect(url_for("auth.home"))


# ── Emergency key rotation ────────────────────────────────────────────────────

@auth_bp.route("/emergency-rotated")
@login_required
def emergency_rotated():
    new_key = session.pop("emergency_new", None)
    if not new_key:
        return redirect(url_for("secrets.index"))
    return render_template("emergency_rotated.html", new_key=new_key)
