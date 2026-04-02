"""Secrets routes: list, add, edit, delete keys."""
from __future__ import annotations

import html as html_mod

from flask import Blueprint, render_template, request, redirect, url_for, flash

from vault.helpers import (
    login_required, get_vault, add_msg, verify_identity,
    TAG_STYLES, get_tag, set_tag, tag_badge,
)

secrets_bp = Blueprint("secrets", __name__)


@secrets_bp.route("/vault")
@login_required
def index():
    vault  = get_vault()
    keys   = vault.list_keys()
    values = {k: vault.get(k) for k in keys}
    tags   = {k: get_tag(vault, k) for k in keys}
    badges = {k: tag_badge(tags[k]) for k in keys}

    # Build tag filter options
    used_tags = sorted(set(tags.values()))
    filter_opts = "<option value=''>All types</option>" + "".join(
        "<option value='{t}'>{label}</option>".format(t=t, label=TAG_STYLES.get(t, ("Other",))[0])
        for t in used_tags
    )

    return render_template(
        "secrets.html",
        keys=keys, values=values,
        tags=tags, badges=badges, filter_opts=filter_opts,
    )


@secrets_bp.route("/vault/add", methods=["GET", "POST"])
@login_required
def add_key():
    if request.method == "POST":
        key   = request.form.get("key", "").strip().upper()
        value = request.form.get("value", "").strip()
        tag   = request.form.get("tag", "other").strip()
        if not key or not value:
            flash("Both key and value are required")
            return render_template("secret_form.html", editing=False, key_name=key,
                                   key_value=value, current_tag=tag, tag_styles=TAG_STYLES)
        vault = get_vault()
        vault.set(key, value)
        set_tag(vault, key, tag)
        add_msg("ok", "Key '{}' saved.".format(key))
        return redirect(url_for("secrets.index"))
    return render_template("secret_form.html", editing=False, key_name="",
                           key_value="", current_tag="other", tag_styles=TAG_STYLES)


@secrets_bp.route("/vault/edit/<key>", methods=["GET", "POST"])
@login_required
def edit_key(key):
    vault = get_vault()
    if request.method == "GET":
        try:
            current = vault.get(key)
        except KeyError:
            return redirect(url_for("secrets.index"))
        current_tag = get_tag(vault, key)
        return render_template("secret_form.html", editing=True, key_name=key,
                               key_value=current, current_tag=current_tag, tag_styles=TAG_STYLES)

    if "guard_pwd" not in request.form:
        new_value = request.form.get("value", "").strip()
        new_tag   = request.form.get("tag", "other").strip()
        if not new_value:
            flash("Value cannot be empty")
            return render_template("secret_form.html", editing=True, key_name=key,
                                   key_value="", current_tag=new_tag, tag_styles=TAG_STYLES)
        extra = (
            '<input type="hidden" name="new_value" value="{v}">'
            '<input type="hidden" name="new_tag" value="{t}">'
        ).format(v=html_mod.escape(new_value, quote=True),
                 t=html_mod.escape(new_tag, quote=True))
        return render_template(
            "guard.html",
            action_label="update {}".format(key),
            extra_fields=extra, error="", warning=""
        )

    pwd       = request.form.get("guard_pwd", "").strip()
    code      = request.form.get("code", "").strip()
    new_value = request.form.get("new_value", "").strip()
    new_tag   = request.form.get("new_tag", "other").strip()
    if not verify_identity(pwd, code):
        extra = (
            '<input type="hidden" name="new_value" value="{v}">'
            '<input type="hidden" name="new_tag" value="{t}">'
        ).format(v=html_mod.escape(new_value, quote=True),
                 t=html_mod.escape(new_tag, quote=True))
        return render_template(
            "guard.html",
            action_label="update {}".format(key),
            extra_fields=extra,
            error="Wrong password or authenticator code.", warning=""
        )
    vault.set(key, new_value)
    set_tag(vault, key, new_tag)
    add_msg("ok", "Key '{}' updated.".format(key))
    return redirect(url_for("secrets.index"))


@secrets_bp.route("/vault/delete/<key>", methods=["GET", "POST"])
@login_required
def delete_key(key):
    if request.method == "GET":
        return render_template(
            "guard.html",
            action_label="delete {}".format(key),
            extra_fields="", error="",
            warning="You are about to permanently delete <strong>{}</strong>. This cannot be undone.".format(key)
        )
    pwd  = request.form.get("guard_pwd", "").strip()
    code = request.form.get("code", "").strip()
    if not verify_identity(pwd, code):
        return render_template(
            "guard.html",
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
    return redirect(url_for("secrets.index"))
