"""REST API routes for Jogi Vault."""
from __future__ import annotations

import secrets
import functools
from typing import Optional

from flask import Blueprint, request, jsonify, current_app

from src.vault import Vault, VaultError

api_bp = Blueprint("api", __name__)

_API_TOKEN_KEY = "__api_token__"


def _load_api_token() -> Optional[str]:
    pwd = current_app.config.get("_backup_pwd")
    if not pwd:
        return None
    try:
        return Vault(password=pwd, _skip_totp=True).get_or_none(_API_TOKEN_KEY)
    except Exception:
        return None


def api_auth(f):
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
    pwd = current_app.config.get("_backup_pwd")
    if not pwd:
        raise RuntimeError("Vault is locked. Login to the UI or set VAULT_PASSWORD env var.")
    return Vault(password=pwd, _skip_totp=True, namespace=ns)


@api_bp.route("/api/v1/secret/<key>")
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


@api_bp.route("/api/v1/secrets")
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


@api_bp.route("/api/v1/namespaces")
@api_auth
def api_list_namespaces():
    return jsonify({"namespaces": Vault.list_namespaces()})
