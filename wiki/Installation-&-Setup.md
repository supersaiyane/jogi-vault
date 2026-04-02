# Installation & Setup

## Prerequisites

**Required:**
- Python 3.11 or later
- pip (Python package manager)

**Required Python packages:**
- flask, cryptography, pyotp, qrcode[pil], pypng, rich

**Optional (for backup):**
- google-auth, google-auth-oauthlib, google-api-python-client, APScheduler

**Optional (for Docker):**
- Docker, docker-compose

---

## Installation

### Option A — Local Python

```bash
# From the project root (jogi-explains/)
pip install -r requirements.txt

# Start the vault UI
make -f vault/Makefile up

# Or directly:
PYTHONPATH=. python vault/ui.py
```

### Option B — Docker (recommended for production)

```bash
# Build and start
docker-compose up vault-ui -d

# Check it's running
docker-compose logs vault-ui

# Open in browser
open http://localhost:5111
```

### Option C — Standalone Docker (vault only)

```bash
cd vault/
docker-compose up -d
open http://localhost:5111
```

---

## First-Time Setup (Web Wizard)

When you visit `http://localhost:5111` for the first time, the setup wizard guides you through three steps:

### Step 1 — Set Master Password

- Choose a strong password (16+ characters recommended)
- Use a mix of uppercase, lowercase, numbers, symbols
- This password is **NEVER stored** — remember it or use a password manager
- Type it again to confirm
- Click "Continue"

**Behind the scenes:**
- Random 16-byte salt generated → `vault.salt`
- PBKDF2(password, salt) → 32-byte encryption key
- Empty `{}` encrypted → `vault.enc`

### Step 2 — Set Up TOTP 2FA

- A QR code appears on screen
- Open your authenticator app (Google Authenticator, Authy, YubiKey, 1Password, etc.)
- Scan the QR code
- Enter the 6-digit code shown in app
- Click "Verify & Continue"

**Behind the scenes:**
- Random TOTP secret generated (Base32 encoded)
- Encrypted with AES-256-GCM → `vault.totp`

### Step 3 — Save Emergency Keys

Two keys are displayed. **SAVE BOTH IMMEDIATELY.**

| Key | Format | Purpose |
|-----|--------|---------|
| Recovery Key | `JOGI-XXXXX-XXXXX-XXXXX-XXXXX` | Resets master password if forgotten |
| Emergency Key | `EMRG-XXXXX-XXXXX-XXXXX-XXXXX` | One-time TOTP bypass if you lose your authenticator |

> Store both in a password manager. They are shown **once** and cannot be retrieved.

Click "I have saved both keys" to enter the vault.

### After Setup — Generate a Machine Token

1. Go to the **API tab** in the web UI
2. Click **"Generate Machine Token"**
3. Copy the `VLT-...` token shown (displayed once!)
4. Add to your `.env` file or shell:

```bash
export VAULT_PASSWORD=VLT-xxxxxxxxxxxxxxxxxxx
```

### Files Created After Setup

```
vault/data/vault.enc        ← encrypted secrets (empty for now)
vault/data/vault.salt       ← password salt
vault/data/vault.totp       ← encrypted TOTP secret
vault/data/vault.recovery   ← recovery key bundle
vault/data/vault.emergency  ← emergency key hash
```

---

## Next Steps

- [Secret Management](Secret-Management) — start adding API keys
- [Machine Tokens](Machine-Tokens) — set up automated access
- [Backup & Restore](Backup-&-Restore) — configure Google Drive backups
