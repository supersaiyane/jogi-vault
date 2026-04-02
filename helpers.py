"""Shared helpers for the Jogi Vault web UI."""
from __future__ import annotations

import io
import base64
import html as html_mod
from functools import wraps
from typing import Optional

import qrcode
from qrcode.image.pure import PyPNGImage
from flask import session, redirect, url_for, render_template, make_response

from src.vault import (
    Vault, VaultError, TOTPInvalidError, TOTPRequiredError,
)
from vault.middleware.session_crypto import _session_decrypt


# ── Login guard ──────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "vault_password" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


# ── Vault access ─────────────────────────────────────────────────────────────

def get_vault(namespace=None):
    ns = namespace or session.get("vault_ns", "default")
    return Vault(password=_session_decrypt(), _skip_totp=True, namespace=ns)


def current_ns():
    return session.get("vault_ns", "default")


# ── Messages ─────────────────────────────────────────────────────────────────

def add_msg(cat, text):
    session.setdefault("_msgs", []).append((cat, text))


# ── QR code ──────────────────────────────────────────────────────────────────

def uri_to_qr_img_tag(uri):
    buf = io.BytesIO()
    img = qrcode.make(uri, image_factory=PyPNGImage, box_size=8, border=3)
    img.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return '<img src="data:image/png;base64,{}" style="width:240px;height:240px;" alt="QR code">'.format(b64)


# ── Identity verification ────────────────────────────────────────────────────

def verify_identity(password, code):
    try:
        Vault(password=password, totp_code=code or None)
        return True
    except (VaultError, TOTPInvalidError, TOTPRequiredError):
        return False


# ── Error page ───────────────────────────────────────────────────────────────

def error_page(code, headline, body_text):
    html = render_template("error.html", code=code, headline=headline, body_text=body_text)
    return make_response(html, code)


# ── Tag system ───────────────────────────────────────────────────────────────

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


def tag_key(key_name):
    return "__tag_{}__".format(key_name)


def get_tag(vault, key_name):
    return vault.get_or_none(tag_key(key_name)) or "other"


def set_tag(vault, key_name, tag):
    if tag and tag in TAG_STYLES and tag != "other":
        vault.set(tag_key(key_name), tag)
    else:
        try:
            vault.delete(tag_key(key_name))
        except KeyError:
            pass


def tag_badge(tag):
    label, color, bg = TAG_STYLES.get(tag, TAG_STYLES["other"])
    return (
        "<span style='font-size:.68rem;padding:.2rem .6rem;border-radius:20px;"
        "background:{bg};color:{color};border:1px solid {color};"
        "white-space:nowrap;font-weight:600;letter-spacing:.02em;"
        "text-transform:uppercase'>{label}</span>"
    ).format(bg=bg, color=color, label=label)
