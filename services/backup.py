#!/usr/bin/env python3
"""
Jogi Vault — Google Drive Backup Manager

Handles:
  - Google Drive OAuth2 (client credentials stored outside vault.enc
    so emergency restore works even if vault is corrupted)
  - Auto-backup vault/data/ on a configurable interval via APScheduler
  - Restore from Drive backup with email verification
  - Gmail SMTP for verification codes

Vault keys stored (__ prefix = hidden from list_keys):
  __backup_enabled__           "true" / "false"
  __backup_frequency_hours__   integer as string
  __backup_last_run__          ISO-8601 UTC timestamp
  __backup_email__             Gmail address used for SMTP + restore codes
  __backup_smtp_pass__         Gmail App Password (encrypted in vault.enc)
  __backup_gdrive_token__      JSON OAuth token (encrypted in vault.enc)

OAuth client credentials (client_id + client_secret) are stored in
vault/data/backup-oauth.json — NOT inside vault.enc — so that emergency
restore works even when vault.enc is missing or corrupted.
"""
from __future__ import annotations

import io
import json
import smtplib
import zipfile
import secrets
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False

from src.vault import Vault, VAULT_DIR

# ── Constants ─────────────────────────────────────────────────────────────────

SCOPES          = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_NAME     = "JogiVault-Backups"
MAX_BACKUPS     = 10
OAUTH_FILE      = VAULT_DIR / "backup-oauth.json"   # client creds — commit-safe

# Vault key names
_K_ENABLED    = "__backup_enabled__"
_K_FREQUENCY  = "__backup_frequency_hours__"
_K_LAST_RUN   = "__backup_last_run__"
_K_EMAIL      = "__backup_email__"
_K_SMTP       = "__backup_smtp_pass__"
_K_TOKEN      = "__backup_gdrive_token__"


class BackupError(Exception):
    pass


class BackupManager:
    """Orchestrates Drive backup, email verification, and scheduled jobs."""

    def __init__(self, vault: Optional[Vault] = None):
        self.vault = vault

    # ── OAuth config (outside vault.enc for emergency restore) ───────────────

    @staticmethod
    def save_oauth_config(client_id: str, client_secret: str) -> None:
        """Persist OAuth client credentials to vault/data/backup-oauth.json."""
        VAULT_DIR.mkdir(exist_ok=True)
        OAUTH_FILE.write_text(json.dumps({
            "client_id":     client_id.strip(),
            "client_secret": client_secret.strip(),
        }))

    @staticmethod
    def load_oauth_config() -> Optional[dict]:
        if not OAUTH_FILE.exists():
            return None
        try:
            return json.loads(OAUTH_FILE.read_text())
        except Exception:
            return None

    @staticmethod
    def oauth_configured() -> bool:
        cfg = BackupManager.load_oauth_config()
        return bool(cfg and cfg.get("client_id") and cfg.get("client_secret"))

    # ── Vault config ──────────────────────────────────────────────────────────

    def get_config(self) -> dict:
        def _g(k: str, default: str = "") -> str:
            return (self.vault.get_or_none(k) or default) if self.vault else default
        return {
            "enabled":          _g(_K_ENABLED, "false") == "true",
            "frequency_hours":  int(_g(_K_FREQUENCY, "4")),
            "last_run":         _g(_K_LAST_RUN, ""),
            "email":            _g(_K_EMAIL, ""),
            "smtp_configured":  bool(_g(_K_SMTP)),
            "gdrive_connected": bool(_g(_K_TOKEN)),
            "oauth_configured": BackupManager.oauth_configured(),
        }

    def save_vault_config(self, **kwargs) -> None:
        if not self.vault:
            raise BackupError("No vault instance.")
        mapping = {
            "enabled":   (_K_ENABLED,   lambda v: "true" if v else "false"),
            "frequency": (_K_FREQUENCY, str),
            "email":     (_K_EMAIL,     str),
            "smtp":      (_K_SMTP,      str),
        }
        for k, v in kwargs.items():
            if k in mapping and v is not None:
                key, fn = mapping[k]
                val = fn(v)
                if val:
                    self.vault.set(key, val)

    # ── Google Drive OAuth ────────────────────────────────────────────────────

    def get_auth_url(self, redirect_uri: str) -> str:
        """Return the Google OAuth consent URL."""
        if not GDRIVE_AVAILABLE:
            raise BackupError("google-api-python-client is not installed.")
        cfg = self.load_oauth_config()
        if not cfg:
            raise BackupError("OAuth credentials not configured. Save Client ID + Secret first.")
        flow = self._make_flow(cfg, redirect_uri)
        url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        return url

    def complete_auth(self, code: str, redirect_uri: str) -> None:
        """Exchange auth code for tokens and store encrypted in vault."""
        if not GDRIVE_AVAILABLE:
            raise BackupError("google-api-python-client is not installed.")
        cfg  = self.load_oauth_config()
        flow = self._make_flow(cfg, redirect_uri)
        flow.fetch_token(code=code)
        creds = flow.credentials
        token = {
            "token":         creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri":     creds.token_uri,
            "client_id":     creds.client_id,
            "client_secret": creds.client_secret,
            "scopes":        list(creds.scopes) if creds.scopes else SCOPES,
        }
        if self.vault:
            self.vault.set(_K_TOKEN, json.dumps(token))

    def disconnect_gdrive(self) -> None:
        if self.vault:
            try:
                self.vault.delete(_K_TOKEN)
            except KeyError:
                pass

    # ── Backup / Restore ──────────────────────────────────────────────────────

    def backup_now(self) -> str:
        """Zip vault/data/ and upload to Google Drive. Returns backup filename."""
        service   = self._drive()
        folder_id = self._folder(service)
        ts        = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
        name      = "jogi-vault-{}.zip".format(ts)
        buf       = io.BytesIO(self._zip())
        media     = MediaIoBaseUpload(buf, mimetype="application/zip")
        service.files().create(
            body={"name": name, "parents": [folder_id]},
            media_body=media,
            fields="id",
        ).execute()
        if self.vault:
            self.vault.set(_K_LAST_RUN, datetime.now(timezone.utc).isoformat())
        self._prune(service, folder_id)
        return name

    def list_backups(self) -> list:
        """Return list of backups on Drive: [{id, name, created, size_kb}]."""
        try:
            service   = self._drive()
            folder_id = self._folder(service)
        except Exception:
            return []
        res = service.files().list(
            q="'{}' in parents and trashed=false".format(folder_id),
            orderBy="createdTime desc",
            fields="files(id,name,createdTime,size)",
            pageSize=20,
        ).execute()
        out = []
        for f in res.get("files", []):
            out.append({
                "id":      f["id"],
                "name":    f["name"],
                "created": f.get("createdTime", "")[:10],
                "size_kb": round(int(f.get("size", 0)) / 1024, 1),
            })
        return out

    def restore_backup(self, file_id: str) -> None:
        """Download backup from Drive and extract to vault/data/."""
        service = self._drive()
        buf     = io.BytesIO()
        dl      = MediaIoBaseDownload(buf, service.files().get_media(fileId=file_id))
        done = False
        while not done:
            _, done = dl.next_chunk()
        buf.seek(0)
        self._unzip(buf.read())

    # ── Email verification ────────────────────────────────────────────────────

    def send_restore_code(self, to_email: str) -> str:
        """Send a 6-digit verification code via Gmail. Returns the code."""
        if not self.vault:
            raise BackupError("No vault instance.")
        from_email = self.vault.get_or_none(_K_EMAIL)
        smtp_pass  = self.vault.get_or_none(_K_SMTP)
        if not from_email or not smtp_pass:
            raise BackupError("Email not configured in backup settings.")
        code = "{:06d}".format(secrets.randbelow(1_000_000))
        msg  = MIMEMultipart("alternative")
        msg["Subject"] = "Jogi Vault — Restore Verification Code"
        msg["From"]    = from_email
        msg["To"]      = to_email
        body = (
            "Your Jogi Vault restore verification code:\n\n"
            "  {code}\n\n"
            "Valid for 10 minutes.\n"
            "If you did not request a vault restore, ignore this email.\n"
        ).format(code=code)
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(from_email, smtp_pass)
            srv.sendmail(from_email, to_email, msg.as_string())
        return code

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _make_flow(cfg: dict, redirect_uri: str) -> "Flow":
        client_config = {"web": {
            "client_id":     cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }}
        flow = Flow.from_client_config(client_config, scopes=SCOPES)
        flow.redirect_uri = redirect_uri
        return flow

    def _drive(self):
        if not GDRIVE_AVAILABLE:
            raise BackupError("google-api-python-client is not installed.")
        raw = self.vault.get_or_none(_K_TOKEN) if self.vault else None
        if not raw:
            raise BackupError("Google Drive not connected. Go to Backup tab to connect.")
        td    = json.loads(raw)
        creds = Credentials(
            token=td["token"], refresh_token=td["refresh_token"],
            token_uri=td["token_uri"], client_id=td["client_id"],
            client_secret=td["client_secret"], scopes=td["scopes"],
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            td["token"] = creds.token
            if self.vault:
                self.vault.set(_K_TOKEN, json.dumps(td))
        return build("drive", "v3", credentials=creds)

    @staticmethod
    def _folder(service) -> str:
        q   = "name='{}' and mimeType='application/vnd.google-apps.folder' and trashed=false".format(FOLDER_NAME)
        res = service.files().list(q=q, fields="files(id)", pageSize=1).execute()
        files = res.get("files", [])
        if files:
            return files[0]["id"]
        f = service.files().create(
            body={"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
            fields="id",
        ).execute()
        return f["id"]

    @staticmethod
    def _zip() -> bytes:
        """Zip all vault/data/ files except backup-oauth.json."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in VAULT_DIR.iterdir():
                if p.is_file() and p.name != "backup-oauth.json":
                    zf.write(p, p.name)
        buf.seek(0)
        return buf.read()

    @staticmethod
    def _unzip(data: bytes) -> None:
        VAULT_DIR.mkdir(exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            vault_root = VAULT_DIR.resolve()
            for info in zf.infolist():
                target = (VAULT_DIR / info.filename).resolve()
                if not target.is_relative_to(vault_root):
                    raise BackupError(
                        "Unsafe path in backup archive: {}".format(info.filename)
                    )
            zf.extractall(VAULT_DIR)

    @staticmethod
    def _prune(service, folder_id: str) -> None:
        """Keep only MAX_BACKUPS most recent; delete the rest."""
        res = service.files().list(
            q="'{}' in parents and trashed=false".format(folder_id),
            orderBy="createdTime desc",
            fields="files(id)",
            pageSize=50,
        ).execute()
        for f in res.get("files", [])[MAX_BACKUPS:]:
            try:
                service.files().delete(fileId=f["id"]).execute()
            except Exception:
                pass
