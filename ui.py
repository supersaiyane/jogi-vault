#!/usr/bin/env python3
"""
Jogi Explains — Vault Web UI
Run:  python vault/ui.py   OR   make vault-ui   OR   docker-compose up vault-ui
Then: http://localhost:5111
"""
from __future__ import annotations

import os
import secrets
import base64
import io

import qrcode
from qrcode.image.pure import PyPNGImage
from flask import (
    Flask, render_template_string, request,
    redirect, url_for, session, flash,
)

from src.vault import (
    Vault, VaultError, TOTPInvalidError,
    TOTPRequiredError, EmergencyKeyUsed,
)
from vault.backup import BackupManager, BackupError
from flask import jsonify

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

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ── Auto-unlock from environment (needed for API without UI login) ─────────────
def _try_env_unlock():
    pwd = os.environ.get("VAULT_PASSWORD", "").strip()
    if pwd and Vault.is_initialised():
        try:
            Vault(password=pwd, _skip_totp=True)
            app.config["_backup_pwd"] = pwd
        except Exception:
            pass

_try_env_unlock()


# ── Error pages ───────────────────────────────────────────────────────────────

def _error_page(code, headline, body_text):
    html = (
        "<!doctype html><html><head><meta charset=utf-8>"
        "<title>Jogi Vault &mdash; " + str(code) + "</title>"
        + CSS +
        "</head><body>"
        "<div class=cw><div class=box style='text-align:center'>"
        "<div style='font-size:4rem;margin-bottom:1rem'>&#128274;</div>"
        "<h1 style='font-size:2rem;color:#6c63ff;margin-bottom:.5rem'>" + headline + "</h1>"
        "<p style='color:#666;font-size:.95rem;margin-bottom:2rem;line-height:1.6'>" + body_text + "</p>"
        "<a href='/login' class='btn bp' style='margin-right:.8rem'>Back to Vault</a>"
        "<a href='/' class='btn bg'>Home</a>"
        "</div></div></body></html>"
    )
    from flask import make_response
    return make_response(html, code)


@app.errorhandler(404)
def not_found(e):
    return _error_page(
        404,
        "Page not found",
        "This page doesn&rsquo;t exist in the vault.<br>"
        "Maybe the URL changed, or you followed a stale link."
    )


@app.errorhandler(500)
def server_error(e):
    return _error_page(
        500,
        "Something went wrong",
        "An unexpected error occurred inside the vault.<br>"
        "Your data is safe &mdash; this is just a server hiccup."
    )


@app.errorhandler(403)
def forbidden(e):
    return _error_page(
        403,
        "Access denied",
        "You don&rsquo;t have permission to access this page.<br>"
        "Please log in first."
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "vault_password" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_vault(namespace=None):
    ns = namespace or session.get("vault_ns", "default")
    return Vault(password=session["vault_password"], _skip_totp=True, namespace=ns)


def current_ns():
    return session.get("vault_ns", "default")


def uri_to_qr_img_tag(uri):
    buf = io.BytesIO()
    img = qrcode.make(uri, image_factory=PyPNGImage, box_size=8, border=3)
    img.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return '<img src="data:image/png;base64,{}" style="width:240px;height:240px;" alt="QR code">'.format(b64)


def add_msg(cat, text):
    session.setdefault("_msgs", []).append((cat, text))


@app.context_processor
def inject_helpers():
    def pop_msgs():
        msgs = session.pop("_msgs", [])
        return "".join(
            '<div class="flash {}">{}</div>'.format(c, t) for c, t in msgs
        )
    return {"pop_msgs": pop_msgs}


# ── Scheduler ─────────────────────────────────────────────────────────────────

def _start_backup_scheduler(password: str, frequency_hours: int) -> None:
    """(Re)schedule the auto-backup job."""
    if not SCHEDULER_AVAILABLE or _scheduler is None:
        return
    app.config["_backup_pwd"] = password
    _scheduler.add_job(
        _run_scheduled_backup,
        trigger=IntervalTrigger(hours=frequency_hours),
        id="vault_backup",
        replace_existing=True,
    )


def _run_scheduled_backup() -> None:
    pwd = app.config.get("_backup_pwd")
    if not pwd:
        return
    try:
        vault = Vault(password=pwd, _skip_totp=True)
        bm    = BackupManager(vault)
        cfg   = bm.get_config()
        if cfg["enabled"] and cfg["gdrive_connected"]:
            name = bm.backup_now()
            app.logger.info("Scheduled backup: %s", name)
    except Exception as exc:
        app.logger.error("Scheduled backup failed: %s", exc)


# ── Styles + nav ──────────────────────────────────────────────────────────────

CSS = """<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0d0d14;color:#e2e2f0;min-height:100vh}
nav{background:#13131f;border-bottom:1px solid #2a2a3d;padding:0 2rem;height:56px;
    display:flex;align-items:center;justify-content:space-between}
.brand{font-weight:700;font-size:1.1rem;color:#6c63ff}
.brand span{color:#e2e2f0}
.nav-tabs{display:flex;gap:.5rem;align-items:center}
.nav-link{font-size:.85rem;color:#888;text-decoration:none;border:1px solid #2a2a3d;
          padding:.3rem .8rem;border-radius:6px}
.nav-link:hover{color:#e2e2f0;border-color:#555}
.nav-link.active{color:#6c63ff;border-color:#6c63ff}
.nav-lock{font-size:.85rem;color:#888;text-decoration:none;border:1px solid #2a2a3d;
          padding:.3rem .8rem;border-radius:6px;margin-left:1rem}
.nav-lock:hover{color:#e07070;border-color:#e07070}
.page{max-width:900px;margin:2.5rem auto;padding:0 1.5rem}
.cw{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}
.box{width:100%;max-width:460px}
.box.wide{max-width:540px}
.box h1{font-size:1.6rem;color:#6c63ff;margin-bottom:.25rem}
.sub{color:#666;font-size:.88rem;margin-bottom:1.8rem}
.card{background:#13131f;border:1px solid #2a2a3d;border-radius:12px;padding:2rem;margin-bottom:1.5rem}
.card h2{font-size:1rem;color:#a09aff;margin-bottom:1.4rem}
.card h2 .badge{font-size:.72rem;padding:.2rem .55rem;border-radius:20px;
                font-weight:600;margin-left:.6rem;vertical-align:middle}
.badge-ok{background:#1a3a2a;color:#74c69d;border:1px solid #2d6a4f}
.badge-warn{background:#3a3a1a;color:#ffd060;border:1px solid #6a6a2d}
.badge-err{background:#3a1a1a;color:#e07070;border:1px solid #6a2d2d}
label{display:block;font-size:.82rem;color:#888;margin-bottom:.35rem}
input[type=text],input[type=password],select{width:100%;padding:.65rem .9rem;background:#0d0d14;
  border:1px solid #2a2a3d;border-radius:8px;color:#e2e2f0;font-size:.95rem;outline:none;transition:border .2s}
input:focus,select:focus{border-color:#6c63ff}
.fr{margin-bottom:1.1rem}
.btn{display:inline-block;padding:.6rem 1.3rem;border-radius:8px;font-size:.9rem;font-weight:600;
     cursor:pointer;border:none;text-decoration:none;transition:opacity .15s}
.btn:hover{opacity:.85}
.bp{background:#6c63ff;color:#fff}
.bd{background:#c0392b;color:#fff}
.bg{background:transparent;color:#888;border:1px solid #2a2a3d}
.bg:hover{color:#e2e2f0;border-color:#555}
.bg2{background:transparent;color:#6c63ff;border:1px solid #6c63ff}
.bw{background:#1a3a2a;color:#74c69d;border:1px solid #2d6a4f}
.bs{padding:.35rem .8rem;font-size:.8rem}
.flash{padding:.75rem 1rem;border-radius:8px;margin-bottom:1.2rem;font-size:.9rem}
.flash.ok{background:#1a3a2a;border:1px solid #2d6a4f;color:#74c69d}
.flash.err{background:#3a1a1a;border:1px solid #6a2d2d;color:#e07070}
.flash.warn{background:#3a3a1a;border:1px solid #6a6a2d;color:#ffd060}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem}
.topbar h1{font-size:1.2rem}
.cnt{color:#555;font-size:.85rem;margin-left:.5rem}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th{text-align:left;padding:.6rem 1rem;border-bottom:1px solid #2a2a3d;
   color:#6c63ff;font-size:.78rem;text-transform:uppercase;letter-spacing:.06em}
td{padding:.7rem 1rem;border-bottom:1px solid #1c1c2e}
tr:last-child td{border-bottom:none}
tr:hover td{background:#16162a}
.kn{font-family:monospace;color:#a09aff}
.vc{font-family:monospace;font-size:.85rem;color:#555}
.vc.on{color:#e2e2f0;word-break:break-all}
.empty{text-align:center;padding:3rem;color:#555;font-size:.9rem}
.steps{display:flex;gap:.5rem;margin-bottom:2rem}
.step{flex:1;height:4px;border-radius:2px;background:#2a2a3d}
.step.done{background:#6c63ff}
.step.act{background:#a09aff}
.kb{background:#0d0d14;border:2px solid #6c63ff;border-radius:10px;
    padding:1.2rem 1.5rem;text-align:center;font-family:monospace;
    font-size:1.2rem;letter-spacing:.1em;color:#fff;margin:.6rem 0}
.hint{font-size:.82rem;color:#555;margin-top:.4rem}
.qw{text-align:center;margin:1rem 0}
.ci{letter-spacing:.2em;font-size:1.3rem;text-align:center}
.stat-row{display:flex;align-items:center;justify-content:space-between;
           padding:.6rem 0;border-bottom:1px solid #1c1c2e;font-size:.9rem}
.stat-row:last-child{border-bottom:none}
.stat-label{color:#888}
.stat-val{color:#e2e2f0;font-family:monospace;font-size:.85rem}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
</style>"""


# ── Key tag system ────────────────────────────────────────────────────────────

TAG_STYLES = {
    "api_key":      ("API Key",       "#6c63ff", "#16163a"),
    "password":     ("Password",      "#e07070", "#3a1a1a"),
    "rsa_private":  ("RSA Private",   "#ff6b6b", "#3a1515"),
    "rsa_public":   ("RSA Public",    "#74c69d", "#1a3a2a"),
    "access_token": ("Access Token",  "#ffd060", "#3a3a1a"),
    "secret":       ("Secret",        "#a09aff", "#1a1a3a"),
    "url":          ("URL / Endpoint","#4ecdc4", "#1a3a3a"),
    "email":        ("Email",         "#aaaaaa", "#2a2a2a"),
    "certificate":  ("Certificate",   "#f0a500", "#3a2a1a"),
    "other":        ("Other",         "#555555", "#1c1c2e"),
}

TAG_SELECT_OPTIONS = "".join(
    "<option value='{k}'>{label}</option>".format(k=k, label=v[0])
    for k, v in TAG_STYLES.items()
)


def _tag_key(key_name):
    return "__tag_{}__".format(key_name)


def _get_tag(vault, key_name):
    return vault.get_or_none(_tag_key(key_name)) or "other"


def _set_tag(vault, key_name, tag):
    if tag and tag in TAG_STYLES and tag != "other":
        vault.set(_tag_key(key_name), tag)
    else:
        try:
            vault.delete(_tag_key(key_name))
        except KeyError:
            pass


def _tag_badge(tag):
    label, color, bg = TAG_STYLES.get(tag, TAG_STYLES["other"])
    return (
        "<span style='font-size:.7rem;padding:.15rem .5rem;border-radius:20px;"
        "background:{bg};color:{color};border:1px solid {color};"
        "white-space:nowrap;font-weight:600'>{label}</span>"
    ).format(bg=bg, color=color, label=label)


def _nav(active="secrets"):
    sa  = " class='nav-link active'" if active == "secrets" else " class='nav-link'"
    ba  = " class='nav-link active'" if active == "backup"  else " class='nav-link'"
    aa  = " class='nav-link active'" if active == "api"     else " class='nav-link'"
    ns  = current_ns()
    all_ns = Vault.list_namespaces()
    ns_opts = "".join(
        "<option value='{n}'{sel}>{n}</option>".format(
            n=n, sel=" selected" if n == ns else ""
        )
        for n in all_ns
    )
    return (
        "<nav>"
        "<div class='brand'>Jogi <span>Vault</span></div>"
        "<div class='nav-tabs'>"
        "<a" + sa + " href='/vault'>Secrets</a>"
        "<a" + ba + " href='/backup'>Backup</a>"
        "<a" + aa + " href='/api-settings'>API</a>"
        "<form method=post action='/vault/switch-ns' style='display:inline;margin-left:.5rem'>"
        "<select name=ns onchange='this.form.submit()' "
        "style='background:#0d0d14;color:#a09aff;border:1px solid #2a2a3d;"
        "border-radius:6px;padding:.25rem .5rem;font-size:.82rem;cursor:pointer'>"
        + ns_opts +
        "</select>"
        "</form>"
        "<a class='btn bg bs' href='/vault/new-ns' "
        "style='font-size:.78rem;padding:.25rem .6rem;margin-left:.3rem'>+ NS</a>"
        "<a class='nav-lock' href='/logout'>Lock</a>"
        "</div>"
        "</nav>"
    )


# ── Setup wizard ──────────────────────────────────────────────────────────────

def _vault_exists_page():
    """Shown when someone tries to run setup but a vault already exists."""
    html = (
        "<!doctype html><html><head><meta charset=utf-8>"
        "<title>Jogi Vault &mdash; Already set up</title>"
        + CSS +
        "</head><body>"
        "<div class=cw><div class=box style='text-align:center'>"
        "<div style='font-size:3.5rem;margin-bottom:1rem'>&#128272;</div>"
        "<h1 style='font-size:1.8rem;color:#6c63ff;margin-bottom:.5rem'>Vault already exists</h1>"
        "<p style='color:#666;font-size:.9rem;margin-bottom:2rem;line-height:1.6'>"
        "A vault is already configured on this machine.<br>"
        "Login with your master password to access it."
        "</p>"
        "<a href='/login' class='btn bp' style='display:block;text-align:center;margin-bottom:.8rem'>"
        "Go to Login &rarr;</a>"
        "<p style='color:#444;font-size:.78rem;margin-top:1.2rem'>"
        "Want to start fresh? Delete <code style='color:#888'>vault/data/</code> files and restart."
        "</p>"
        "</div></div></body></html>"
    )
    return html


@app.route("/setup/password", methods=["GET", "POST"])
def setup_password():
    if Vault.is_initialised():
        return render_template_string(_vault_exists_page())
    if request.method == "POST":
        pwd1 = request.form.get("pwd1", "").strip()
        pwd2 = request.form.get("pwd2", "").strip()
        if not pwd1:
            flash("Password cannot be empty")
        elif pwd1 != pwd2:
            flash("Passwords do not match")
        else:
            session["setup_pwd"] = pwd1
            return redirect(url_for("setup_totp"))
    return render_template_string(
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault</title>"
        + CSS + "</head><body>"
        "<div class=cw><div class=box>"
        "<h1>Jogi Vault</h1><p class=sub>First time setup &mdash; step 1 of 3</p>"
        "{% for m in get_flashed_messages() %}<div class='flash err'>{{m}}</div>{% endfor %}"
        "<div class=steps><div class='step act'></div><div class=step></div><div class=step></div></div>"
        "<div class=card><h2>Set your master password</h2>"
        "<form method=post>"
        "<div class=fr><label>Password</label>"
        "<input type=password name=pwd1 autofocus placeholder='Choose a strong password'></div>"
        "<div class=fr><label>Confirm password</label>"
        "<input type=password name=pwd2 placeholder='Type it again'></div>"
        "<button class='btn bp' style='width:100%;margin-top:.5rem'>Continue &rarr;</button>"
        "</form></div></div></div></body></html>"
    )


@app.route("/setup/totp", methods=["GET", "POST"])
def setup_totp():
    if Vault.is_initialised():
        return render_template_string(_vault_exists_page())
    pwd = session.get("setup_pwd")
    if not pwd:
        return redirect(url_for("setup_password"))

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
            return redirect(url_for("setup_done"))
        error = "Wrong code — check your authenticator and try again."

    tmpl = (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault</title>"
        + CSS + "</head><body>"
        "<div class=cw><div class='box wide'>"
        "<h1>Jogi Vault</h1><p class=sub>First time setup &mdash; step 2 of 3</p>"
        "<div class=steps><div class='step done'></div><div class='step act'></div><div class=step></div></div>"
        "<div class=card><h2>Scan with your Authenticator</h2>"
        "<p style='color:#888;font-size:.88rem;margin-bottom:1rem'>"
        "Works with YubiKey, Google Authenticator, Microsoft Authenticator, Authy, 1Password, or any TOTP app.</p>"
        "<div class=qw>{{ qr_img | safe }}</div>"
        "<p style='color:#444;font-size:.75rem;word-break:break-all;margin-bottom:1rem'>{{ uri }}</p>"
        "{% if error %}<div class='flash err'>{{ error }}</div>{% endif %}"
        "<form method=post><div class=fr><label>Enter the 6-digit code to confirm</label>"
        "<input type=text name=code autofocus maxlength=6 inputmode=numeric"
        " autocomplete=one-time-code placeholder=000000 class=ci></div>"
        "<button class='btn bp' style='width:100%;margin-top:.5rem'>Verify &amp; Continue &rarr;</button>"
        "</form></div></div></div></body></html>"
    )
    return render_template_string(tmpl, qr_img=qr_img, uri=uri, error=error)


@app.route("/setup/done", methods=["GET", "POST"])
def setup_done():
    if Vault.is_initialised() and "setup_recovery" not in session:
        return render_template_string(_vault_exists_page())
    recovery  = session.get("setup_recovery", "")
    emergency = session.get("setup_emergency", "")
    if request.method == "POST":
        for k in ("setup_recovery", "setup_emergency", "setup_pwd"):
            session.pop(k, None)
        add_msg("ok", "Vault ready. Login with your password + authenticator code.")
        return redirect(url_for("login"))
    tmpl = (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault</title>"
        + CSS + "</head><body>"
        "<div class=cw><div class='box wide'>"
        "<h1>Jogi Vault</h1><p class=sub>First time setup &mdash; step 3 of 3</p>"
        "<div class=steps><div class='step done'></div><div class='step done'></div><div class='step act'></div></div>"
        "<div class=card>"
        "<h2 style='color:#ffd060'>Save these keys &mdash; shown only once</h2>"
        "<p style='color:#888;font-size:.88rem;margin-bottom:1.4rem'>"
        "Store both in a password manager, secure notes, or print them out.</p>"
        "<label>Recovery Key <span style='color:#555'>&mdash; resets your password if forgotten</span></label>"
        "<div class=kb>{{ recovery }}</div>"
        "<label style='margin-top:1.2rem;display:block'>Emergency Key"
        " <span style='color:#555'>&mdash; one-time TOTP bypass if you lose your authenticator</span></label>"
        "<div class='kb' style='border-color:#e07070'>{{ emergency }}</div>"
        "<p class=hint>Emergency key regenerates after each use.</p>"
        "<form method=post style='margin-top:1.5rem'>"
        "<button class='btn bp' style='width:100%'>I have saved both keys &mdash; Enter the vault</button>"
        "</form></div></div></div></body></html>"
    )
    return render_template_string(tmpl, recovery=recovery, emergency=emergency)


# ── Login ─────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    if not Vault.is_initialised():
        tmpl = (
            "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault</title>"
            + CSS + "</head><body>"
            "<div class=cw><div class=box>"
            "<h1>Jogi Vault</h1>"
            "<p class=sub>Your encrypted secret manager</p>"
            "{{ pop_msgs() | safe }}"
            "<div class=card>"
            "<p style='color:#888;font-size:.9rem;margin-bottom:1.5rem'>"
            "No vault found. Set up a new vault to securely store your API keys and credentials.</p>"
            "<a href='/setup/password' class='btn bp' style='width:100%;display:block;text-align:center'>"
            "Create New Vault &rarr;</a>"
            "</div>"
            "<p style='color:#555;font-size:.8rem;text-align:center;margin-top:1rem'>"
            "Encrypted with AES &bull; TOTP 2FA &bull; Recovery key included</p>"
            "</div></div></body></html>"
        )
        return render_template_string(tmpl)
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not Vault.is_initialised():
        return redirect(url_for("home"))
    error = ""
    if request.method == "POST":
        pwd  = request.form.get("password", "").strip()
        code = request.form.get("code", "").strip() or None
        try:
            Vault(password=pwd, totp_code=code)
            session["vault_password"] = pwd
            _maybe_start_scheduler(pwd)
            return redirect(url_for("index"))
        except EmergencyKeyUsed as e:
            session["vault_password"] = pwd
            session["emergency_new"]  = e.new_key
            _maybe_start_scheduler(pwd)
            return redirect(url_for("emergency_rotated"))
        except TOTPInvalidError:
            error = "Wrong authenticator code."
        except TOTPRequiredError:
            error = "This vault requires an authenticator code."
        except VaultError:
            error = "Wrong password."
    tmpl = (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault</title>"
        + CSS + "</head><body>"
        "<div class=cw><div class=box>"
        "<h1>Jogi Vault</h1><p class=sub>Enter your credentials to unlock</p>"
        "{% if error %}<div class='flash err'>{{ error }}</div>{% endif %}"
        "<div class=card><form method=post>"
        "<div class=fr><label>Master password</label>"
        "<input type=password name=password autofocus placeholder='&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;'></div>"
        "<div class=fr><label>Authenticator code"
        " <span style='color:#555'>&mdash; or emergency key (EMRG-&hellip;)</span></label>"
        "<input type=text name=code maxlength=30 inputmode=numeric"
        " autocomplete=one-time-code placeholder='6-digit code' style='letter-spacing:.1em'></div>"
        "<button class='btn bp' style='width:100%;margin-top:.5rem'>Unlock</button>"
        "</form></div>"
        "<p style='color:#555;font-size:.8rem;text-align:center;margin-top:1rem'>"
        "Forgot password? Use your recovery key via CLI: <code style='color:#888'>make vault-forgot-password</code>"
        "</p>"
        "</div></div></body></html>"
    )
    return render_template_string(tmpl, error=error)


def _maybe_start_scheduler(password: str) -> None:
    """Start backup scheduler if backup is enabled and Drive is connected."""
    try:
        vault = Vault(password=password, _skip_totp=True)
        bm    = BackupManager(vault)
        cfg   = bm.get_config()
        if cfg["enabled"] and cfg["gdrive_connected"]:
            _start_backup_scheduler(password, cfg["frequency_hours"])
    except Exception:
        pass


@app.route("/emergency-rotated")
@login_required
def emergency_rotated():
    new_key = session.pop("emergency_new", None)
    if not new_key:
        return redirect(url_for("index"))
    tmpl = (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault</title>"
        + CSS + "</head><body>" + _nav()
        + "<div class=cw style='min-height:calc(100vh - 56px)'><div class='box wide'>"
        "<div class=card>"
        "<h2 style='color:#ffd060'>Emergency key used &mdash; here is your new one</h2>"
        "<p style='color:#888;font-size:.88rem;margin:1rem 0'>"
        "Your old key has been consumed. Save this new one immediately.</p>"
        "<div class='kb' style='border-color:#e07070'>{{ new_key }}</div>"
        "<p class=hint>This key grants a one-time TOTP bypass. Keep it safe.</p>"
        "<a href='/vault' class='btn bp' style='display:block;text-align:center;margin-top:1.5rem'>"
        "I have saved it &mdash; continue to vault</a>"
        "</div></div></div></body></html>"
    )
    return render_template_string(tmpl, new_key=new_key)


@app.route("/logout")
def logout():
    app.config.pop("_backup_pwd", None)
    session.clear()
    return redirect(url_for("home"))


# ── Dashboard (Secrets tab) ───────────────────────────────────────────────────

@app.route("/vault")
@login_required
def index():
    vault  = get_vault()
    keys   = vault.list_keys()
    values = {k: vault.get(k)    for k in keys}
    tags   = {k: _get_tag(vault, k) for k in keys}
    badges = {k: _tag_badge(tags[k]) for k in keys}

    # Build tag filter options
    used_tags = sorted(set(tags.values()))
    filter_opts = "<option value=''>All types</option>" + "".join(
        "<option value='{t}'>{label}</option>".format(t=t, label=TAG_STYLES.get(t, ("Other",))[0])
        for t in used_tags
    )

    tmpl = (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault</title>"
        + CSS + "</head><body>" + _nav("secrets")
        + "<div class=page>{{ pop_msgs() | safe }}"
        "<div class=topbar><h1>Secrets <span class=cnt>{{ keys|length }} stored</span></h1>"
        "<div style='display:flex;gap:.8rem;align-items:center'>"
        "<select id=tagfilter onchange='filterByTag(this.value)' style='width:auto;padding:.35rem .7rem;font-size:.82rem'>"
        "{{ filter_opts | safe }}</select>"
        "<a class='btn bp bs' href='/vault/add'>+ Add key</a>"
        "</div></div>"
        "<div class=card>"
        "{% if keys %}"
        "<table id=ktable>"
        "<thead><tr><th>Key</th><th>Type</th><th>Value</th><th>Actions</th></tr></thead>"
        "<tbody>"
        "{% for key in keys %}"
        "<tr data-tag='{{ tags[key] }}'>"
        "<td class=kn>{{ key }}</td>"
        "<td>{{ badges[key] | safe }}</td>"
        "<td class=vc id='v{{ loop.index }}' data-v='{{ values[key] }}'>"
        "&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;</td>"
        "<td>"
        "<button class='btn bg bs' onclick=\"tog('v{{ loop.index }}')\">Show</button> "
        "<a class='btn bg bs' href='/vault/edit/{{ key }}'>Edit</a> "
        "<a class='btn bd bs' href='/vault/delete/{{ key }}'>Del</a>"
        "</td></tr>"
        "{% endfor %}"
        "</tbody></table>"
        "{% else %}<div class=empty>No secrets yet. Click <strong>+ Add key</strong> to start.</div>{% endif %}"
        "</div></div>"
        "<script>"
        "function tog(id){"
        "var td=document.getElementById(id),btn=td.nextElementSibling.querySelector('button');"
        "if(td.classList.contains('on')){"
        "td.innerHTML='&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;';"
        "td.classList.remove('on');btn.textContent='Show';}"
        "else{td.textContent=td.dataset.v;td.classList.add('on');btn.textContent='Hide';}}"
        "function filterByTag(tag){"
        "document.querySelectorAll('#ktable tbody tr').forEach(function(row){"
        "row.style.display=(!tag||row.dataset.tag===tag)?'':'none';});}"
        "</script></body></html>"
    )
    return render_template_string(
        tmpl, keys=keys, values=values,
        tags=tags, badges=badges, filter_opts=filter_opts,
    )


def _verify_identity(password, code):
    try:
        Vault(password=password, totp_code=code or None)
        return True
    except (VaultError, TOTPInvalidError, TOTPRequiredError):
        return False


def _guard_tmpl(action_label, action_url, extra_fields="", warning=""):
    totp_field = (
        "<div class=fr><label>Authenticator code"
        " <span style='color:#555'>&mdash; or emergency key</span></label>"
        "<input type=text name=code maxlength=30 inputmode=numeric"
        " autocomplete=one-time-code placeholder='6-digit code' style='letter-spacing:.1em'></div>"
    )
    return (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault &mdash; Confirm</title>"
        + CSS + "</head><body>" + _nav("secrets")
        + "<div class=cw style='min-height:calc(100vh - 56px)'><div class=box>"
        "{% if warning %}<div class='flash warn'>{{ warning | safe }}</div>{% endif %}"
        "{% if error %}<div class='flash err'>{{ error }}</div>{% endif %}"
        "<div class=card>"
        "<h2 style='color:#ffd060'>Confirm your identity</h2>"
        "<p style='color:#888;font-size:.88rem;margin-bottom:1.4rem'>"
        "Re-enter your credentials to <strong>{{ action_label }}</strong>.</p>"
        "<form method=post>"
        "{{ extra_fields | safe }}"
        "<div class=fr><label>Master password</label>"
        "<input type=password name=guard_pwd autofocus placeholder='&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;'></div>"
        + totp_field +
        "<div style='display:flex;gap:.8rem;margin-top:.5rem'>"
        "<button class='btn bp'>Confirm</button>"
        "<a class='btn bg' href='/vault'>Cancel</a>"
        "</div></form></div>"
        "</div></div></body></html>"
    )


@app.route("/vault/add", methods=["GET", "POST"])
@login_required
def add_key():
    if request.method == "POST":
        key   = request.form.get("key", "").strip().upper()
        value = request.form.get("value", "").strip()
        tag   = request.form.get("tag", "other").strip()
        if not key or not value:
            flash("Both key and value are required")
            return render_template_string(_form_tmpl(), editing=False, key_name=key,
                                          key_value=value, current_tag=tag)
        vault = get_vault()
        vault.set(key, value)
        _set_tag(vault, key, tag)
        add_msg("ok", "Key '{}' saved.".format(key))
        return redirect(url_for("index"))
    return render_template_string(_form_tmpl(), editing=False, key_name="",
                                  key_value="", current_tag="other")


@app.route("/vault/edit/<key>", methods=["GET", "POST"])
@login_required
def edit_key(key):
    vault = get_vault()
    if request.method == "GET":
        try:
            current = vault.get(key)
        except KeyError:
            return redirect(url_for("index"))
        current_tag = _get_tag(vault, key)
        return render_template_string(_form_tmpl(), editing=True, key_name=key,
                                      key_value=current, current_tag=current_tag)

    if "guard_pwd" not in request.form:
        new_value = request.form.get("value", "").strip()
        new_tag   = request.form.get("tag", "other").strip()
        if not new_value:
            flash("Value cannot be empty")
            return render_template_string(_form_tmpl(), editing=True, key_name=key,
                                          key_value="", current_tag=new_tag)
        extra = (
            "<input type=hidden name=new_value value='{v}'>"
            "<input type=hidden name=new_tag value='{t}'>"
        ).format(v=new_value.replace("'", "&#39;"), t=new_tag)
        return render_template_string(
            _guard_tmpl("update {}".format(key), "", extra),
            action_label="update {}".format(key),
            extra_fields=extra, error="", warning=""
        )

    pwd       = request.form.get("guard_pwd", "").strip()
    code      = request.form.get("code", "").strip()
    new_value = request.form.get("new_value", "").strip()
    new_tag   = request.form.get("new_tag", "other").strip()
    if not _verify_identity(pwd, code):
        extra = (
            "<input type=hidden name=new_value value='{v}'>"
            "<input type=hidden name=new_tag value='{t}'>"
        ).format(v=new_value.replace("'", "&#39;"), t=new_tag)
        return render_template_string(
            _guard_tmpl("update {}".format(key), "", extra),
            action_label="update {}".format(key),
            extra_fields=extra,
            error="Wrong password or authenticator code.", warning=""
        )
    vault.set(key, new_value)
    _set_tag(vault, key, new_tag)
    add_msg("ok", "Key '{}' updated.".format(key))
    return redirect(url_for("index"))


@app.route("/vault/delete/<key>", methods=["GET", "POST"])
@login_required
def delete_key(key):
    if request.method == "GET":
        return render_template_string(
            _guard_tmpl("delete {}".format(key), ""),
            action_label="delete {}".format(key),
            extra_fields="", error="",
            warning="You are about to permanently delete <strong>{}</strong>. This cannot be undone.".format(key)
        )
    pwd  = request.form.get("guard_pwd", "").strip()
    code = request.form.get("code", "").strip()
    if not _verify_identity(pwd, code):
        return render_template_string(
            _guard_tmpl("delete {}".format(key), ""),
            action_label="delete {}".format(key),
            extra_fields="",
            error="Wrong password or authenticator code.",
            warning="You are about to permanently delete <strong>{}</strong>.".format(key)
        )
    try:
        get_vault().delete(key)
        add_msg("ok", "Key '{}' deleted.".format(key))
    except KeyError:
        add_msg("err", "Key '{}' not found.".format(key))
    return redirect(url_for("index"))


def _form_tmpl():
    # Build tag select options with selected state
    tag_opts = "".join(
        "<option value='{k}'{sel}>{label}</option>".format(
            k=k, label=v[0],
            sel=" selected" if "{{ current_tag }}" == k else ""
        )
        for k, v in TAG_STYLES.items()
    )
    # Use Jinja2 for selected state
    tag_select = (
        "<select name=tag style='width:100%'>"
        + "".join(
            "<option value='{k}'" + "{% if current_tag == '" + k + "' %} selected{% endif %}" +
            ">{label}</option>".format(k=k, label=v[0])
            for k, v in TAG_STYLES.items()
        )
        + "</select>"
    )
    return (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault</title>"
        + CSS + "</head><body>" + _nav("secrets")
        + "<div class=page>"
        "<div class=topbar><h1>{{ 'Edit' if editing else 'Add' }} key</h1>"
        "<a class='btn bg bs' href='/vault'>&#8592; Back</a></div>"
        "{% for m in get_flashed_messages() %}<div class='flash err'>{{ m }}</div>{% endfor %}"
        "<div class=card><form method=post>"
        "<div class=fr><label>Key name</label>"
        "<input type=text name=key value='{{ key_name }}' placeholder='ANTHROPIC_API_KEY'"
        "{% if editing %} readonly style='color:#555'{% endif %}></div>"
        "<div class=fr><label>Value</label>"
        "<input type=text name=value value='{{ key_value }}' placeholder='sk-ant-api03-...' autocomplete=off></div>"
        "<div class=fr><label>Type / Tag</label>"
        + tag_select +
        "</div>"
        "<div style='display:flex;gap:.8rem;margin-top:.5rem'>"
        "<button class='btn bp'>{{ 'Update' if editing else 'Save' }}</button>"
        "<a class='btn bg' href='/vault'>Cancel</a>"
        "</div></form></div></div></body></html>"
    )


# ── Backup tab ────────────────────────────────────────────────────────────────

@app.route("/backup")
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
                "<td style='color:#888'>{created}</td>"
                "<td style='color:#888'>{size_kb} KB</td>"
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

    tmpl = (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault &mdash; Backup</title>"
        + CSS + "</head><body>" + _nav("backup")
        + "<div class=page>{{ pop_msgs() | safe }}"
        "<div class=topbar><h1>Backup</h1>"
        "<div style='display:flex;gap:.8rem'>" + backup_now_btn + "</div>"
        "</div>"

        # ── Google Drive card ──
        "<div class=card>"
        "<h2>Google Drive " + drive_badge + "</h2>"
        "{% if gdrive_connected %}"
        "<div class=stat-row><span class=stat-label>Status</span><span class=stat-val>Connected &mdash; backups uploading to JogiVault-Backups folder</span></div>"
        "<form method=post action='/backup/gdrive/disconnect' style='margin-top:1.2rem'>"
        "<button class='btn bd bs'>Disconnect Drive</button>"
        "</form>"
        "{% else %}"
        "<p style='color:#888;font-size:.88rem;margin-bottom:1.2rem'>"
        "Connect your Google Drive to enable cloud backups. You need a Google OAuth client ID and secret "
        "(<a href='https://console.cloud.google.com/apis/credentials' target=_blank style='color:#6c63ff'>create one here</a> "
        "with Drive API enabled, redirect URI: <code style='color:#a09aff'>http://localhost:5111/backup/gdrive/callback</code>)."
        "</p>"
        "<form method=post action='/backup/oauth-config'>"
        "<div class='row2'>"
        "<div class=fr><label>Google Client ID</label>"
        "<input type=text name=client_id value='{{ client_id }}' placeholder='xxxxxxxx.apps.googleusercontent.com'></div>"
        "<div class=fr><label>Google Client Secret</label>"
        "<input type=password name=client_secret placeholder='GOCSPX-...'></div>"
        "</div>"
        "<div style='display:flex;gap:.8rem'>"
        "<button class='btn bg'>Save OAuth Config</button>"
        "{% if oauth_configured %}"
        "<a class='btn bp' href='/backup/gdrive/connect'>Connect Google Drive &rarr;</a>"
        "{% endif %}"
        "</div>"
        "</form>"
        "{% endif %}"
        "</div>"

        # ── Email card ──
        "<div class=card>"
        "<h2>Email Verification " + email_badge + "</h2>"
        "<p style='color:#888;font-size:.88rem;margin-bottom:1.2rem'>"
        "Used to verify your identity before restoring a backup. "
        "Use a <a href='https://myaccount.google.com/apppasswords' target=_blank style='color:#6c63ff'>Gmail App Password</a> "
        "&mdash; not your real Gmail password.</p>"
        "<form method=post action='/backup/email-config'>"
        "<div class='row2'>"
        "<div class=fr><label>Gmail address</label>"
        "<input type=text name=email value='{{ email }}' placeholder='you@gmail.com'></div>"
        "<div class=fr><label>Gmail App Password</label>"
        "<input type=password name=smtp placeholder='xxxx xxxx xxxx xxxx'></div>"
        "</div>"
        "<button class='btn bg'>Save Email Config</button>"
        "</form>"
        "</div>"

        # ── Schedule card ──
        "<div class=card>"
        "<h2>Auto-Backup Schedule " + sched_badge + "</h2>"
        "<form method=post action='/backup/schedule'>"
        "<div class='row2'>"
        "<div class=fr><label>Frequency</label>"
        "<select name=frequency>" + freq_opts + "</select>"
        "</div>"
        "<div class=fr><label>Last backup</label>"
        "<input type=text value='" + last_run_str + "' readonly style='color:#555'>"
        "</div>"
        "</div>"
        "<div class=fr style='display:flex;align-items:center;gap:.8rem;margin-bottom:.5rem'>"
        "<input type=checkbox name=enabled id=enb style='width:auto' {{ 'checked' if enabled else '' }}>"
        "<label for=enb style='margin:0;color:#e2e2f0;font-size:.9rem'>Enable automatic backups</label>"
        "</div>"
        "<button class='btn bg'>Save Schedule</button>"
        "</form>"
        "</div>"

        # ── Backup history card ──
        "<div class=card>"
        "<h2>Backup History</h2>"
        + history_html +
        "</div>"

        "</div></body></html>"
    )
    return render_template_string(
        tmpl,
        gdrive_connected=cfg["gdrive_connected"],
        oauth_configured=cfg["oauth_configured"],
        client_id=BackupManager.load_oauth_config().get("client_id", "") if BackupManager.load_oauth_config() else "",
        email=cfg["email"],
        enabled=cfg["enabled"],
    )


@app.route("/backup/oauth-config", methods=["POST"])
@login_required
def backup_oauth_config():
    cid  = request.form.get("client_id", "").strip()
    csec = request.form.get("client_secret", "").strip()
    if not cid or not csec:
        add_msg("err", "Both Client ID and Client Secret are required.")
    else:
        BackupManager.save_oauth_config(cid, csec)
        add_msg("ok", "OAuth config saved. Click 'Connect Google Drive' to authorise.")
    return redirect(url_for("backup_page"))


@app.route("/backup/email-config", methods=["POST"])
@login_required
def backup_email_config():
    email = request.form.get("email", "").strip()
    smtp  = request.form.get("smtp", "").strip()
    if not email:
        add_msg("err", "Gmail address is required.")
        return redirect(url_for("backup_page"))
    bm = BackupManager(get_vault())
    kwargs = {"email": email}
    if smtp:
        kwargs["smtp"] = smtp
    bm.save_vault_config(**kwargs)
    add_msg("ok", "Email config saved.")
    return redirect(url_for("backup_page"))


@app.route("/backup/schedule", methods=["POST"])
@login_required
def backup_schedule():
    enabled   = "enabled" in request.form
    frequency = int(request.form.get("frequency", 4))
    bm        = BackupManager(get_vault())
    bm.save_vault_config(enabled=enabled, frequency=frequency)
    if enabled:
        _start_backup_scheduler(session["vault_password"], frequency)
        add_msg("ok", "Auto-backup enabled — every {} hour(s).".format(frequency))
    else:
        app.config.pop("_backup_pwd", None)
        add_msg("ok", "Auto-backup disabled.")
    return redirect(url_for("backup_page"))


@app.route("/backup/gdrive/connect")
@login_required
def gdrive_connect():
    try:
        redirect_uri = url_for("gdrive_callback", _external=True)
        url = BackupManager(get_vault()).get_auth_url(redirect_uri)
        return redirect(url)
    except BackupError as e:
        add_msg("err", str(e))
        return redirect(url_for("backup_page"))


@app.route("/backup/gdrive/callback")
@login_required
def gdrive_callback():
    code  = request.args.get("code", "")
    error = request.args.get("error", "")
    if error or not code:
        add_msg("err", "Google Drive authorisation was cancelled or failed.")
        return redirect(url_for("backup_page"))
    try:
        redirect_uri = url_for("gdrive_callback", _external=True)
        BackupManager(get_vault()).complete_auth(code, redirect_uri)
        add_msg("ok", "Google Drive connected. Your vault will be backed up automatically.")
    except BackupError as e:
        add_msg("err", str(e))
    return redirect(url_for("backup_page"))


@app.route("/backup/gdrive/disconnect", methods=["POST"])
@login_required
def gdrive_disconnect():
    BackupManager(get_vault()).disconnect_gdrive()
    app.config.pop("_backup_pwd", None)
    add_msg("ok", "Google Drive disconnected. Auto-backup stopped.")
    return redirect(url_for("backup_page"))


@app.route("/backup/now", methods=["POST"])
@login_required
def backup_now():
    try:
        name = BackupManager(get_vault()).backup_now()
        add_msg("ok", "Backup complete: " + name)
    except BackupError as e:
        add_msg("err", str(e))
    except Exception as e:
        add_msg("err", "Backup failed: " + str(e))
    return redirect(url_for("backup_page"))


# ── Restore flow (email verify) ───────────────────────────────────────────────

@app.route("/backup/restore-init/<file_id>", methods=["POST"])
@login_required
def backup_restore_init(file_id):
    """Step 1 — show email entry page to send a verification code."""
    bm  = BackupManager(get_vault())
    cfg = bm.get_config()
    if not cfg["smtp_configured"]:
        add_msg("err", "Email not configured. Add Gmail + App Password in Backup settings first.")
        return redirect(url_for("backup_page"))
    session["restore_file_id"] = file_id
    tmpl = (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault &mdash; Restore</title>"
        + CSS + "</head><body>" + _nav("backup")
        + "<div class=cw style='min-height:calc(100vh - 56px)'><div class=box>"
        "{% if error %}<div class='flash err'>{{ error }}</div>{% endif %}"
        "<div class=card>"
        "<h2 style='color:#ffd060'>Verify before restore</h2>"
        "<p style='color:#888;font-size:.88rem;margin-bottom:1.4rem'>"
        "We will send a 6-digit code to your configured email to confirm this restore.</p>"
        "<form method=post action='/backup/restore-send'>"
        "<div class=fr><label>Send code to email</label>"
        "<input type=text name=email value='{{ email }}' placeholder='you@gmail.com' autofocus></div>"
        "<div style='display:flex;gap:.8rem;margin-top:.5rem'>"
        "<button class='btn bp'>Send Code</button>"
        "<a class='btn bg' href='/backup'>Cancel</a>"
        "</div></form>"
        "</div></div></div></body></html>"
    )
    return render_template_string(tmpl, error="", email=cfg["email"])


@app.route("/backup/restore-send", methods=["POST"])
@login_required
def backup_restore_send():
    """Step 2 — send the email code, show the code entry form."""
    file_id = session.get("restore_file_id", "")
    if not file_id:
        return redirect(url_for("backup_page"))
    to_email = request.form.get("email", "").strip()
    if not to_email:
        add_msg("err", "Email address is required.")
        return redirect(url_for("backup_page"))
    try:
        bm   = BackupManager(get_vault())
        code = bm.send_restore_code(to_email)
        session["restore_code"]  = code
        session["restore_email"] = to_email
    except BackupError as e:
        add_msg("err", str(e))
        return redirect(url_for("backup_page"))
    tmpl = (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault &mdash; Restore</title>"
        + CSS + "</head><body>" + _nav("backup")
        + "<div class=cw style='min-height:calc(100vh - 56px)'><div class=box>"
        "{% if error %}<div class='flash err'>{{ error }}</div>{% endif %}"
        "<div class=card>"
        "<h2 style='color:#ffd060'>Enter verification code</h2>"
        "<p style='color:#888;font-size:.88rem;margin-bottom:1.4rem'>"
        "A 6-digit code was sent to <strong>{{ email }}</strong>. Enter it below to confirm the restore.</p>"
        "<form method=post action='/backup/restore-confirm'>"
        "<div class=fr><label>Verification code</label>"
        "<input type=text name=code autofocus maxlength=6 inputmode=numeric"
        " placeholder=000000 class=ci></div>"
        "<div style='display:flex;gap:.8rem;margin-top:.5rem'>"
        "<button class='btn bp'>Restore Backup</button>"
        "<a class='btn bg' href='/backup'>Cancel</a>"
        "</div></form>"
        "</div></div></div></body></html>"
    )
    return render_template_string(tmpl, error="", email=to_email)


@app.route("/backup/restore-confirm", methods=["POST"])
@login_required
def backup_restore_confirm():
    """Step 3 — verify code and perform the restore."""
    file_id        = session.get("restore_file_id", "")
    expected_code  = session.get("restore_code", "")
    entered_code   = request.form.get("code", "").strip()

    if not file_id or not expected_code:
        add_msg("err", "Restore session expired. Please start over.")
        return redirect(url_for("backup_page"))

    if not secrets.compare_digest(expected_code, entered_code):
        tmpl = (
            "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault &mdash; Restore</title>"
            + CSS + "</head><body>" + _nav("backup")
            + "<div class=cw style='min-height:calc(100vh - 56px)'><div class=box>"
            "<div class='flash err'>Wrong code. Please try again.</div>"
            "<div class=card>"
            "<h2 style='color:#ffd060'>Enter verification code</h2>"
            "<form method=post action='/backup/restore-confirm'>"
            "<div class=fr><label>Verification code</label>"
            "<input type=text name=code autofocus maxlength=6 inputmode=numeric"
            " placeholder=000000 class=ci></div>"
            "<div style='display:flex;gap:.8rem;margin-top:.5rem'>"
            "<button class='btn bp'>Restore Backup</button>"
            "<a class='btn bg' href='/backup'>Cancel</a>"
            "</div></form>"
            "</div></div></div></body></html>"
        )
        return render_template_string(tmpl)

    # Code correct — perform restore
    try:
        BackupManager(get_vault()).restore_backup(file_id)
        session.pop("restore_file_id", None)
        session.pop("restore_code", None)
        session.pop("restore_email", None)
        add_msg("ok", "Vault restored successfully from backup. Your data is back.")
    except Exception as e:
        add_msg("err", "Restore failed: " + str(e))
    return redirect(url_for("backup_page"))


# ── Namespace routes ──────────────────────────────────────────────────────────

@app.route("/vault/switch-ns", methods=["POST"])
@login_required
def switch_ns():
    ns = request.form.get("ns", "default").strip()
    if Vault.is_initialised(ns):
        session["vault_ns"] = ns
    return redirect(url_for("index"))


@app.route("/vault/new-ns", methods=["GET", "POST"])
@login_required
def new_ns():
    error = ""
    if request.method == "POST":
        name = request.form.get("name", "").strip().lower()
        try:
            get_vault("default").create_namespace(name)
            session["vault_ns"] = name
            add_msg("ok", "Namespace '{}' created.".format(name))
            return redirect(url_for("index"))
        except VaultError as e:
            error = str(e)
    tmpl = (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault</title>"
        + CSS + "</head><body>" + _nav("secrets")
        + "<div class=page>"
        "<div class=topbar><h1>New Namespace</h1>"
        "<a class='btn bg bs' href='/vault'>&#8592; Back</a></div>"
        "{% if error %}<div class='flash err'>{{ error }}</div>{% endif %}"
        "<div class=card>"
        "<p style='color:#888;font-size:.88rem;margin-bottom:1.2rem'>"
        "A namespace is a separate encrypted store — same password, isolated keys.<br>"
        "Use it to separate keys by project, environment, or team.</p>"
        "<form method=post>"
        "<div class=fr><label>Namespace name <span style='color:#555'>(lowercase, hyphens ok)</span></label>"
        "<input type=text name=name autofocus placeholder='my-project'></div>"
        "<div style='display:flex;gap:.8rem'>"
        "<button class='btn bp'>Create</button>"
        "<a class='btn bg' href='/vault'>Cancel</a>"
        "</div></form></div></div></body></html>"
    )
    return render_template_string(tmpl, error=error)


@app.route("/vault/delete-ns/<ns>", methods=["POST"])
@login_required
def delete_ns(ns):
    try:
        get_vault("default").delete_namespace(ns)
        if session.get("vault_ns") == ns:
            session["vault_ns"] = "default"
        add_msg("ok", "Namespace '{}' deleted.".format(ns))
    except VaultError as e:
        add_msg("err", str(e))
    return redirect(url_for("index"))


# ── REST API ──────────────────────────────────────────────────────────────────
#
#   All endpoints require:  Authorization: Bearer <token>
#   Token is generated from the API settings page in the UI.
#   If VAULT_PASSWORD env var is set the vault is pre-unlocked on startup,
#   so the API works without anyone being logged into the UI.
#
#   GET  /api/v1/secret/<KEY>          → {"key":..,"value":..,"namespace":..}
#   GET  /api/v1/secret/<KEY>?ns=work  → same but from "work" namespace
#   GET  /api/v1/secrets               → {"keys":[...],"namespace":..}
#   GET  /api/v1/namespaces            → {"namespaces":[...]}
# ─────────────────────────────────────────────────────────────────────────────

_API_TOKEN_KEY = "__api_token__"


def _load_api_token() -> Optional[str]:
    pwd = app.config.get("_backup_pwd")
    if not pwd:
        return None
    try:
        return Vault(password=pwd, _skip_totp=True).get_or_none(_API_TOKEN_KEY)
    except Exception:
        return None


def api_auth(f):
    import functools
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing Authorization: Bearer <token> header"}), 401
        token   = auth[7:].strip()
        stored  = _load_api_token()
        if not stored:
            return jsonify({"error": "API not enabled. Generate a token from the API settings page."}), 503
        if not secrets.compare_digest(token, stored):
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


def _api_vault(ns: str = "default") -> Vault:
    pwd = app.config.get("_backup_pwd")
    if not pwd:
        raise RuntimeError("Vault is locked. Login to the UI or set VAULT_PASSWORD env var.")
    return Vault(password=pwd, _skip_totp=True, namespace=ns)


@app.route("/api/v1/secret/<key>")
@api_auth
def api_get_secret(key):
    ns = request.args.get("ns", "default")
    try:
        value = _api_vault(ns).get(key.upper())
        return jsonify({"key": key.upper(), "value": value, "namespace": ns})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except KeyError:
        return jsonify({"error": "Key '{}' not found in namespace '{}'".format(key, ns)}), 404
    except VaultError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/secrets")
@api_auth
def api_list_secrets():
    ns = request.args.get("ns", "default")
    try:
        vault = _api_vault(ns)
        keys  = vault.list_keys()
        return jsonify({"keys": keys, "namespace": ns, "count": len(keys)})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except VaultError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/namespaces")
@api_auth
def api_list_namespaces():
    return jsonify({"namespaces": Vault.list_namespaces()})


# ── API settings page ─────────────────────────────────────────────────────────

@app.route("/api-settings")
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
        is_current = " style='color:#6c63ff'" if n == ns else ""
        del_btn = (
            "<form method=post action='/vault/delete-ns/{n}' style='display:inline'>"
            "<button class='btn bd bs' onclick=\"return confirm('Delete namespace {n}?')\">Delete</button>"
            "</form>"
        ).format(n=n) if n != "default" else "<span style='color:#444'>—</span>"
        ns_rows += (
            "<tr><td class=kn{style}>{n}</td>"
            "<td style='color:#555;font-size:.82rem'>{enc}</td>"
            "<td>{del_btn}</td></tr>"
        ).format(style=is_current, n=n,
                 enc="vault-{}.enc".format(n) if n != "default" else "vault.enc",
                 del_btn=del_btn)

    token_display = token[:8] + "..." + token[-4:] if len(token) > 16 else (token or "Not generated")

    tmpl = (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault &mdash; API</title>"
        + CSS + "</head><body>" + _nav("api")
        + "<div class=page>{{ pop_msgs() | safe }}"
        "<div class=topbar><h1>API &amp; Namespaces</h1></div>"

        # ── Machine token card ──
        "<div class=card>"
        "<h2>Machine Token "
        "{% if machine_active %}<span class='badge badge-ok'>Active</span>"
        "{% else %}<span class='badge badge-err'>Not generated</span>{% endif %}"
        "</h2>"
        "<p style='color:#888;font-size:.88rem;margin-bottom:1.2rem'>"
        "A machine token (<code>VLT-&hellip;</code>) hides your real password behind a derived key. "
        "Put it in <code>VAULT_PASSWORD=VLT-&hellip;</code> in docker-compose, <code>.env</code>, or CI/CD. "
        "Even if someone reads that file, they cannot derive your master password — "
        "and without <code>vault/data/vault.token</code> the token is useless.</p>"
        "<div class=stat-row><span class=stat-label>Status</span>"
        "<span class=stat-val>"
        "{% if machine_active %}Active &mdash; VLT-&hellip; token can unlock the vault"
        "{% else %}No token issued yet{% endif %}"
        "</span></div>"
        "<div style='display:flex;gap:.8rem;margin-top:1.2rem'>"
        "<form method=post action='/api-settings/machine-token'>"
        "<button class='btn {% if machine_active %}bg{% else %}bp{% endif %}'>"
        "{% if machine_active %}Rotate Token{% else %}Generate Machine Token{% endif %}"
        "</button>"
        "</form>"
        "{% if machine_active %}"
        "<form method=post action='/api-settings/machine-token/revoke'>"
        "<button class='btn bd'>Revoke</button>"
        "</form>"
        "{% endif %}"
        "</div>"
        "</div>"

        # ── API token card ──
        "<div class=card>"
        "<h2>REST API Token</h2>"
        "<p style='color:#888;font-size:.88rem;margin-bottom:1.2rem'>"
        "Use this token to read secrets from your code without loading everything into env vars. "
        "The vault must be unlocked (UI login or <code>VAULT_PASSWORD</code> env var).</p>"
        "{% if token %}"
        "<div class=stat-row><span class=stat-label>Token</span>"
        "<span class=stat-val style='font-size:.78rem'>{{ token_display }}</span></div>"
        "<div class=stat-row><span class=stat-label>Base URL</span>"
        "<span class=stat-val>{{ base }}/api/v1</span></div>"
        "{% endif %}"
        "<form method=post action='/api-settings/generate' style='margin-top:1.2rem'>"
        "<button class='btn {% if token %}bg{% else %}bp{% endif %}'>"
        "{% if token %}Regenerate Token{% else %}Generate API Token{% endif %}"
        "</button>"
        "</form>"
        "</div>"

        # ── Code examples card ──
        "{% if token %}"
        "<div class=card>"
        "<h2>Usage examples</h2>"
        "<p style='color:#888;font-size:.82rem;margin-bottom:1rem'>Replace <code>YOUR_TOKEN</code> with your actual token.</p>"
        "<label style='margin-bottom:.5rem'>Python</label>"
        "<pre style='background:#0a0a10;border:1px solid #2a2a3d;border-radius:8px;"
        "padding:1rem;font-size:.8rem;overflow-x:auto;color:#a09aff;margin-bottom:1.2rem'>"
        "import requests\n\n"
        "VAULT = '{{ base }}/api/v1'\n"
        "TOKEN = 'YOUR_TOKEN'\n\n"
        "def get_secret(key, ns='default'):\n"
        "    r = requests.get(\n"
        "        f'{VAULT}/secret/{key}',\n"
        "        params={'ns': ns},\n"
        "        headers={'Authorization': f'Bearer {TOKEN}'}\n"
        "    )\n"
        "    return r.json()['value']\n\n"
        "api_key = get_secret('ANTHROPIC_API_KEY')\n"
        "stripe  = get_secret('STRIPE_KEY', ns='payments')"
        "</pre>"
        "<label style='margin-bottom:.5rem'>curl</label>"
        "<pre style='background:#0a0a10;border:1px solid #2a2a3d;border-radius:8px;"
        "padding:1rem;font-size:.8rem;overflow-x:auto;color:#a09aff;margin-bottom:1.2rem'>"
        "# Get a single key\n"
        "curl {{ base }}/api/v1/secret/ANTHROPIC_API_KEY \\\n"
        "     -H 'Authorization: Bearer YOUR_TOKEN'\n\n"
        "# From a specific namespace\n"
        "curl '{{ base }}/api/v1/secret/STRIPE_KEY?ns=payments' \\\n"
        "     -H 'Authorization: Bearer YOUR_TOKEN'\n\n"
        "# List all keys\n"
        "curl {{ base }}/api/v1/secrets \\\n"
        "     -H 'Authorization: Bearer YOUR_TOKEN'"
        "</pre>"
        "</div>"
        "{% endif %}"

        # ── Namespaces card ──
        "<div class=card>"
        "<h2>Namespaces</h2>"
        "<p style='color:#888;font-size:.88rem;margin-bottom:1.2rem'>"
        "Each namespace is a separate encrypted key store — same password, isolated secrets.</p>"
        "<table><thead><tr><th>Name</th><th>File</th><th>Action</th></tr></thead>"
        "<tbody>" + ns_rows + "</tbody></table>"
        "<a class='btn bg bs' href='/vault/new-ns' style='margin-top:1.2rem;display:inline-block'>"
        "+ New Namespace</a>"
        "</div>"

        "</div></body></html>"
    )
    return render_template_string(
        tmpl, token=token, token_display=token_display,
        base=base, machine_active=machine_active,
    )


@app.route("/api-settings/machine-token", methods=["POST"])
@login_required
def machine_token_generate():
    vault = get_vault("default")
    token = vault.generate_machine_token()
    session["show_machine_token"] = token
    return redirect(url_for("machine_token_reveal"))


@app.route("/api-settings/machine-token/revoke", methods=["POST"])
@login_required
def machine_token_revoke():
    get_vault("default").revoke_machine_token()
    app.config.pop("_backup_pwd", None)
    add_msg("ok", "Machine token revoked. All automated access using VLT-… is now blocked.")
    return redirect(url_for("api_settings"))


@app.route("/api-settings/machine-token/show", methods=["GET", "POST"])
@login_required
def machine_token_reveal():
    token = session.pop("show_machine_token", None)
    if not token:
        return redirect(url_for("api_settings"))
    if request.method == "POST":
        return redirect(url_for("api_settings"))
    tmpl = (
        "<!doctype html><html><head><meta charset=utf-8>"
        "<title>Jogi Vault &mdash; Machine Token</title>"
        + CSS + "</head><body>" + _nav("api")
        + "<div class=cw style='min-height:calc(100vh - 56px)'><div class='box wide'>"
        "<div class=card>"
        "<h2 style='color:#ffd060'>Your machine token &mdash; shown once</h2>"
        "<p style='color:#888;font-size:.88rem;margin:1rem 0'>"
        "This token hides your real password. Use it everywhere you would have used "
        "<code>VAULT_PASSWORD=yourpassword</code>. "
        "Store it securely — it will not be shown again.</p>"
        "<div class=kb style='font-size:.78rem;letter-spacing:.03em;word-break:break-all'>{{ token }}</div>"
        "<div style='background:#13131f;border:1px solid #2a2a3d;border-radius:8px;"
        "padding:1.2rem;margin-top:1.2rem'>"
        "<p style='color:#6c63ff;font-size:.8rem;font-weight:600;margin-bottom:.6rem'>Usage examples</p>"
        "<p style='color:#555;font-size:.78rem;margin-bottom:.35rem'>docker-compose.yml / .env</p>"
        "<pre style='color:#a09aff;font-size:.8rem'>VAULT_PASSWORD={{ token }}</pre>"
        "<p style='color:#555;font-size:.78rem;margin:.6rem 0 .35rem'>Shell</p>"
        "<pre style='color:#a09aff;font-size:.8rem'>export VAULT_PASSWORD={{ token }}</pre>"
        "<p style='color:#555;font-size:.78rem;margin:.6rem 0 .35rem'>Python</p>"
        "<pre style='color:#a09aff;font-size:.8rem'>"
        "from src.vault import Vault\n"
        "vault = Vault(password='{{ token }}')"
        "</pre>"
        "</div>"
        "<p class=hint style='margin-top:.8rem'>"
        "Your real password is never stored. "
        "Rotating or revoking this token instantly blocks all automated access.</p>"
        "<form method=post style='margin-top:1.5rem'>"
        "<button class='btn bp' style='width:100%'>I have saved it &mdash; go to API settings</button>"
        "</form></div></div></div></body></html>"
    )
    return render_template_string(tmpl, token=token)


@app.route("/api-settings/generate", methods=["POST"])
@login_required
def api_generate_token():
    token = secrets.token_urlsafe(40)
    vault = get_vault("default")
    vault.set(_API_TOKEN_KEY, token)
    # Also update app config so API works immediately
    app.config["_backup_pwd"] = session["vault_password"]
    add_msg("ok", "New API token generated. Copy it from the display below.")
    session["show_api_token"] = token
    return redirect(url_for("api_token_reveal"))


@app.route("/api-settings/token", methods=["GET", "POST"])
@login_required
def api_token_reveal():
    token = session.pop("show_api_token", None)
    if not token:
        return redirect(url_for("api_settings"))
    if request.method == "POST":
        return redirect(url_for("api_settings"))
    tmpl = (
        "<!doctype html><html><head><meta charset=utf-8><title>Jogi Vault &mdash; API Token</title>"
        + CSS + "</head><body>" + _nav("api")
        + "<div class=cw style='min-height:calc(100vh - 56px)'><div class='box wide'>"
        "<div class=card>"
        "<h2 style='color:#ffd060'>Your API token &mdash; shown once</h2>"
        "<p style='color:#888;font-size:.88rem;margin:1rem 0'>"
        "Copy and store this token securely. It will not be shown again in full.</p>"
        "<div class=kb style='font-size:.85rem;letter-spacing:.05em;word-break:break-all'>{{ token }}</div>"
        "<p class=hint>Pass it as <code>Authorization: Bearer &lt;token&gt;</code> in API requests.</p>"
        "<form method=post style='margin-top:1.5rem'>"
        "<button class='btn bp' style='width:100%'>I have saved it &mdash; go to API settings</button>"
        "</form></div></div></div></body></html>"
    )
    return render_template_string(tmpl, token=token)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("VAULT_UI_PORT", 5111))
    print("\n  Jogi Vault UI -> http://localhost:{}\n".format(port))
    app.run(host="0.0.0.0", port=port, debug=False)
