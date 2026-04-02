# Backup & Restore

## Setup

### 1. Create Google Cloud OAuth credentials

1. Go to [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials)
2. Create an OAuth 2.0 Client ID (type: Web Application)
3. Enable the Google Drive API
4. Add authorized redirect URI: `http://localhost:5111/backup/gdrive/callback`

### 2. Configure in Vault UI → Backup tab

1. Enter Client ID and Client Secret
2. Click "Save OAuth Config"
3. Click "Connect Google Drive" → authorize in browser

### 3. Configure email verification

1. Enter your Gmail address
2. Create a [Gmail App Password](https://myaccount.google.com/apppasswords)
3. Enter the App Password (not your real Gmail password)
4. Click "Save Email Config"

### 4. Enable automatic backups

1. Check "Enable automatic backups"
2. Select frequency: 1, 2, 4, 8, 12, or 24 hours
3. Click "Save Schedule"

---

## Backup Flow

```
Trigger: manual button OR automatic schedule
      │
      ▼
Zip all files in vault/data/ (except backup-oauth.json)
      │
      ▼
Connect to Google Drive (OAuth2 refresh token)
      │
      ▼
Find or create "JogiVault-Backups" folder
      │
      ▼
Upload zip: jogi-vault-2026-04-02-103000.zip
      │
      ▼
Save timestamp: last_run = now
      │
      ▼
Prune: keep only 10 most recent backups
```

**Manual backup:**
```bash
make -f vault/Makefile backup P=xxx
```

---

## Restore Flow (with email verification)

```
1. Backup tab → click "Restore" next to a backup
      │
      ▼
2. Enter email → click "Send Code"
      │
      ▼
3. 6-digit code sent via Gmail SMTP
      │
      ▼
4. Enter code → click "Restore Backup"
      │
      ├── Wrong code → try again
      │
      ▼
5. Code verified (constant-time comparison)
      │
      ▼
6. Download zip from Google Drive
      │
      ▼
7. Validate all file paths (zip traversal protection)
      │
      ▼
8. Extract to vault/data/ (overwrites existing files)
      │
      ▼
9. "Vault restored successfully" — may need to re-login
```

---

## Important Notes

- Backup files are encrypted at rest (vault.enc is AES-256-GCM)
- OAuth client credentials are stored in `backup-oauth.json` (outside vault.enc so emergency restore works even if the vault is corrupted)
- The backup scheduler only runs while the vault UI is running
- Restoring replaces ALL vault/data/ files with the backup contents
