"""Settings routes: API settings, machine tokens, namespaces."""
from __future__ import annotations

import secrets

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app

from src.vault import Vault, VaultError
from vault.helpers import login_required, get_vault, current_ns, add_msg
from vault.middleware.session_crypto import _session_decrypt

settings_bp = Blueprint("settings", __name__)

_API_TOKEN_KEY = "__api_token__"


@settings_bp.route("/api-settings")
@login_required
def api_settings():
    vault          = get_vault("default")
    token          = vault.get_or_none(_API_TOKEN_KEY) or ""
    base           = request.host_url.rstrip("/")
    ns             = current_ns()
    all_ns         = Vault.list_namespaces()
    machine_active = vault.machine_token_active()

    # Build namespace management table
    ns_rows = ""
    for n in all_ns:
        is_current = " style='color:var(--accent)'" if n == ns else ""
        del_btn = (
            "<form method=post action='/vault/delete-ns/{n}' style='display:inline'>"
            "<button class='btn bd bs' onclick=\"return confirm('Delete namespace {n}?')\">Delete</button>"
            "</form>"
        ).format(n=n) if n != "default" else "<span style='color:var(--text-muted)'>—</span>"
        ns_rows += (
            "<tr><td class=kn{style}>{n}</td>"
            "<td style='color:#555;font-size:.82rem'>{enc}</td>"
            "<td>{del_btn}</td></tr>"
        ).format(style=is_current, n=n,
                 enc="vault-{}.enc".format(n) if n != "default" else "vault.enc",
                 del_btn=del_btn)

    token_display = token[:8] + "..." + token[-4:] if len(token) > 16 else (token or "Not generated")

    return render_template(
        "api_settings.html",
        token=token, token_display=token_display,
        base=base, machine_active=machine_active,
        ns_rows=ns_rows,
    )


@settings_bp.route("/api-settings/machine-token", methods=["POST"])
@login_required
def machine_token_generate():
    vault = get_vault("default")
    token = vault.generate_machine_token()
    session["show_machine_token"] = token
    return redirect(url_for("settings.machine_token_reveal"))


@settings_bp.route("/api-settings/machine-token/revoke", methods=["POST"])
@login_required
def machine_token_revoke():
    get_vault("default").revoke_machine_token()
    current_app.config.pop("_backup_pwd", None)
    add_msg("ok", "Machine token revoked. All automated access using VLT-... is now blocked.")
    return redirect(url_for("settings.api_settings"))


@settings_bp.route("/api-settings/machine-token/show", methods=["GET", "POST"])
@login_required
def machine_token_reveal():
    token = session.pop("show_machine_token", None)
    if not token:
        return redirect(url_for("settings.api_settings"))
    if request.method == "POST":
        return redirect(url_for("settings.api_settings"))
    return render_template("machine_token_reveal.html", token=token)


@settings_bp.route("/api-settings/generate", methods=["POST"])
@login_required
def api_generate_token():
    token = secrets.token_urlsafe(40)
    vault = get_vault("default")
    vault.set(_API_TOKEN_KEY, token)
    # Also update app config so API works immediately
    current_app.config["_backup_pwd"] = _session_decrypt()
    add_msg("ok", "New API token generated. Copy it from the display below.")
    session["show_api_token"] = token
    return redirect(url_for("settings.api_token_reveal"))


@settings_bp.route("/api-settings/token", methods=["GET", "POST"])
@login_required
def api_token_reveal():
    token = session.pop("show_api_token", None)
    if not token:
        return redirect(url_for("settings.api_settings"))
    if request.method == "POST":
        return redirect(url_for("settings.api_settings"))
    return render_template("api_token_reveal.html", token=token)


# ── Namespace routes ──────────────────────────────────────────────────────────

@settings_bp.route("/vault/switch-ns", methods=["POST"])
@login_required
def switch_ns():
    ns = request.form.get("ns", "default").strip()
    if Vault.is_initialised(ns):
        session["vault_ns"] = ns
    return redirect(url_for("secrets.index"))


@settings_bp.route("/vault/new-ns", methods=["GET", "POST"])
@login_required
def new_ns():
    error = ""
    if request.method == "POST":
        name = request.form.get("name", "").strip().lower()
        try:
            get_vault("default").create_namespace(name)
            session["vault_ns"] = name
            add_msg("ok", "Namespace '{}' created.".format(name))
            return redirect(url_for("secrets.index"))
        except VaultError as e:
            error = str(e)
    return render_template("namespace_new.html", error=error)


@settings_bp.route("/vault/delete-ns/<ns>", methods=["POST"])
@login_required
def delete_ns(ns):
    try:
        get_vault("default").delete_namespace(ns)
        if session.get("vault_ns") == ns:
            session["vault_ns"] = "default"
        add_msg("ok", "Namespace '{}' deleted.".format(ns))
    except VaultError as e:
        add_msg("err", str(e))
    return redirect(url_for("secrets.index"))
