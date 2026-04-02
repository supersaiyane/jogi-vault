"""Backup routes: backup page, Google Drive, email config, restore flow."""
from __future__ import annotations

import secrets

from flask import Blueprint, render_template, request, redirect, url_for, session

from vault.helpers import login_required, get_vault, add_msg
from vault.services.backup import BackupManager, BackupError
from vault.middleware.session_crypto import _session_decrypt

backup_bp = Blueprint("backup", __name__)


@backup_bp.route("/backup")
@login_required
def backup_page():
    vault   = get_vault()
    bm      = BackupManager(vault)
    cfg     = bm.get_config()
    backups = bm.list_backups() if cfg["gdrive_connected"] else []

    # Status badges
    drive_badge  = "<span class='badge badge-ok'>Connected</span>" if cfg["gdrive_connected"] else "<span class='badge badge-warn'>Not connected</span>"
    email_badge  = "<span class='badge badge-ok'>Configured</span>" if cfg["smtp_configured"]  else "<span class='badge badge-warn'>Not set</span>"
    sched_badge  = "<span class='badge badge-ok'>Active</span>"     if cfg["enabled"]           else "<span class='badge badge-err'>Off</span>"
    last_run_str = cfg["last_run"][:19].replace("T", " ") + " UTC" if cfg["last_run"] else "Never"

    # Backup history table
    if backups:
        rows = ""
        for b in backups:
            rows += (
                "<tr><td class=kn style='font-size:.82rem'>{name}</td>"
                "<td style='color:var(--text-secondary)'>{created}</td>"
                "<td style='color:var(--text-secondary)'>{size_kb} KB</td>"
                "<td>"
                "<form method=post action='/backup/restore-init/{fid}' style='display:inline'>"
                "<button class='btn bw bs'>Restore</button>"
                "</form>"
                "</td></tr>"
            ).format(name=b["name"], created=b["created"], size_kb=b["size_kb"], fid=b["id"])
        history_html = (
            "<table><thead><tr><th>Backup</th><th>Date</th><th>Size</th><th>Action</th></tr></thead>"
            "<tbody>" + rows + "</tbody></table>"
        )
    else:
        history_html = "<div class=empty>No backups found on Google Drive.</div>"

    # Frequency select options
    freq_opts = ""
    for h, label in [(1, "Every 1 hour"), (2, "Every 2 hours"), (4, "Every 4 hours"),
                     (8, "Every 8 hours"), (12, "Every 12 hours"), (24, "Every 24 hours")]:
        sel = " selected" if cfg["frequency_hours"] == h else ""
        freq_opts += "<option value='{h}'{sel}>{label}</option>".format(h=h, sel=sel, label=label)

    # Backup now button (only if Drive connected)
    backup_now_btn = ""
    if cfg["gdrive_connected"]:
        backup_now_btn = (
            "<form method=post action='/backup/now' style='display:inline'>"
            "<button class='btn bw'>&#9729; Backup Now</button>"
            "</form>"
        )

    return render_template(
        "backup.html",
        gdrive_connected=cfg["gdrive_connected"],
        oauth_configured=cfg["oauth_configured"],
        client_id=BackupManager.load_oauth_config().get("client_id", "") if BackupManager.load_oauth_config() else "",
        email=cfg["email"],
        enabled=cfg["enabled"],
        drive_badge=drive_badge,
        email_badge=email_badge,
        sched_badge=sched_badge,
        last_run_str=last_run_str,
        history_html=history_html,
        freq_opts=freq_opts,
        backup_now_btn=backup_now_btn,
    )


@backup_bp.route("/backup/oauth-config", methods=["POST"])
@login_required
def backup_oauth_config():
    cid  = request.form.get("client_id", "").strip()
    csec = request.form.get("client_secret", "").strip()
    if not cid or not csec:
        add_msg("err", "Both Client ID and Client Secret are required.")
    else:
        BackupManager.save_oauth_config(cid, csec)
        add_msg("ok", "OAuth config saved. Click 'Connect Google Drive' to authorise.")
    return redirect(url_for("backup.backup_page"))


@backup_bp.route("/backup/email-config", methods=["POST"])
@login_required
def backup_email_config():
    email = request.form.get("email", "").strip()
    smtp  = request.form.get("smtp", "").strip()
    if not email:
        add_msg("err", "Gmail address is required.")
        return redirect(url_for("backup.backup_page"))
    bm = BackupManager(get_vault())
    kwargs = {"email": email}
    if smtp:
        kwargs["smtp"] = smtp
    bm.save_vault_config(**kwargs)
    add_msg("ok", "Email config saved.")
    return redirect(url_for("backup.backup_page"))


@backup_bp.route("/backup/schedule", methods=["POST"])
@login_required
def backup_schedule():
    from flask import current_app
    from vault.app import start_backup_scheduler
    enabled   = "enabled" in request.form
    frequency = int(request.form.get("frequency", 4))
    bm        = BackupManager(get_vault())
    bm.save_vault_config(enabled=enabled, frequency=frequency)
    if enabled:
        start_backup_scheduler(_session_decrypt(), frequency)
        add_msg("ok", "Auto-backup enabled — every {} hour(s).".format(frequency))
    else:
        current_app.config.pop("_backup_pwd", None)
        add_msg("ok", "Auto-backup disabled.")
    return redirect(url_for("backup.backup_page"))


@backup_bp.route("/backup/gdrive/connect")
@login_required
def gdrive_connect():
    try:
        redirect_uri = url_for("backup.gdrive_callback", _external=True)
        url = BackupManager(get_vault()).get_auth_url(redirect_uri)
        return redirect(url)
    except BackupError as e:
        add_msg("err", str(e))
        return redirect(url_for("backup.backup_page"))


@backup_bp.route("/backup/gdrive/callback")
@login_required
def gdrive_callback():
    code  = request.args.get("code", "")
    error = request.args.get("error", "")
    if error or not code:
        add_msg("err", "Google Drive authorisation was cancelled or failed.")
        return redirect(url_for("backup.backup_page"))
    try:
        redirect_uri = url_for("backup.gdrive_callback", _external=True)
        BackupManager(get_vault()).complete_auth(code, redirect_uri)
        add_msg("ok", "Google Drive connected. Your vault will be backed up automatically.")
    except BackupError as e:
        add_msg("err", str(e))
    return redirect(url_for("backup.backup_page"))


@backup_bp.route("/backup/gdrive/disconnect", methods=["POST"])
@login_required
def gdrive_disconnect():
    from flask import current_app
    BackupManager(get_vault()).disconnect_gdrive()
    current_app.config.pop("_backup_pwd", None)
    add_msg("ok", "Google Drive disconnected. Auto-backup stopped.")
    return redirect(url_for("backup.backup_page"))


@backup_bp.route("/backup/now", methods=["POST"])
@login_required
def backup_now():
    try:
        name = BackupManager(get_vault()).backup_now()
        add_msg("ok", "Backup complete: " + name)
    except BackupError as e:
        add_msg("err", str(e))
    except Exception as e:
        add_msg("err", "Backup failed: " + str(e))
    return redirect(url_for("backup.backup_page"))


# ── Restore flow (email verify) ──────────────────────────────────────────────

@backup_bp.route("/backup/restore-init/<file_id>", methods=["POST"])
@login_required
def backup_restore_init(file_id):
    """Step 1 — show email entry page to send a verification code."""
    bm  = BackupManager(get_vault())
    cfg = bm.get_config()
    if not cfg["smtp_configured"]:
        add_msg("err", "Email not configured. Add Gmail + App Password in Backup settings first.")
        return redirect(url_for("backup.backup_page"))
    session["restore_file_id"] = file_id
    return render_template("restore_init.html", error="", email=cfg["email"])


@backup_bp.route("/backup/restore-send", methods=["POST"])
@login_required
def backup_restore_send():
    """Step 2 — send the email code, show the code entry form."""
    file_id = session.get("restore_file_id", "")
    if not file_id:
        return redirect(url_for("backup.backup_page"))
    to_email = request.form.get("email", "").strip()
    if not to_email:
        add_msg("err", "Email address is required.")
        return redirect(url_for("backup.backup_page"))
    try:
        bm   = BackupManager(get_vault())
        code = bm.send_restore_code(to_email)
        session["restore_code"]  = code
        session["restore_email"] = to_email
    except BackupError as e:
        add_msg("err", str(e))
        return redirect(url_for("backup.backup_page"))
    return render_template("restore_verify.html", error="", email=to_email)


@backup_bp.route("/backup/restore-confirm", methods=["POST"])
@login_required
def backup_restore_confirm():
    """Step 3 — verify code and perform the restore."""
    file_id        = session.get("restore_file_id", "")
    expected_code  = session.get("restore_code", "")
    entered_code   = request.form.get("code", "").strip()

    if not file_id or not expected_code:
        add_msg("err", "Restore session expired. Please start over.")
        return redirect(url_for("backup.backup_page"))

    if not secrets.compare_digest(expected_code, entered_code):
        return render_template("restore_verify.html",
                               error="Wrong code. Please try again.",
                               email=session.get("restore_email", ""))

    # Code correct — perform restore
    try:
        BackupManager(get_vault()).restore_backup(file_id)
        session.pop("restore_file_id", None)
        session.pop("restore_code", None)
        session.pop("restore_email", None)
        add_msg("ok", "Vault restored successfully from backup. Your data is back.")
    except Exception as e:
        add_msg("err", "Restore failed: " + str(e))
    return redirect(url_for("backup.backup_page"))
