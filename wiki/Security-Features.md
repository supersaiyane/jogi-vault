# Security Features

## Session Encryption

The vault password stored in the Flask session cookie is encrypted with AES-256-GCM using a key derived from the server's secret key.

**Why:** Flask session cookies are signed but NOT encrypted by default. Anyone who intercepts the cookie could read the base64-encoded data. With session encryption, even if someone gets the cookie, they cannot extract the master password.

**How:** `hashlib.sha256(app.secret_key) → AES-256-GCM key → encrypt password before storing in session`

---

## CSRF Protection

All form submissions include a cryptographic CSRF (Cross-Site Request Forgery) token.

**How it works:**
1. A random token is generated per session and stored server-side
2. The `after_request` hook auto-injects the token into every `<form method=post>` in the HTML
3. The `before_request` hook validates the token on every POST request
4. API routes (Bearer token auth) are excluded

**Why:** Prevents attackers from tricking your browser into submitting vault forms from a malicious website.

---

## Login Rate Limiting

Maximum 5 login attempts per IP address within a 5-minute window.

| Setting | Value |
|---------|-------|
| Max attempts | 5 per IP |
| Window | 5 minutes |
| Action on limit | "Too many login attempts" error |

**Why:** Prevents online brute-force attacks against the login page.

---

## Zip Path Traversal Protection

When restoring from a Google Drive backup, all file paths in the zip archive are validated before extraction.

```python
for info in zf.infolist():
    target = (VAULT_DIR / info.filename).resolve()
    if not target.is_relative_to(vault_root):
        raise BackupError("Unsafe path in backup archive")
```

**Why:** A malicious zip with paths like `../../etc/crontab` could write files outside `vault/data/`. The validation rejects any path that escapes the target directory.

---

## Identity Guard on Destructive Operations

Editing or deleting a secret in the web UI requires re-entering your password + TOTP code, even if you're already logged in.

**Why:** If someone accesses your unlocked browser, they can see secrets (limited damage) but cannot change or delete them without knowing the password.

---

## Constant-Time Comparisons

All security-critical comparisons use `secrets.compare_digest()`:
- API token validation
- CSRF token validation
- Emergency key verification
- Restore verification codes

**Why:** Prevents timing attacks where an attacker measures response time to guess tokens character by character.

---

## Pinned Dependencies

Docker image dependencies use version ranges (`>=X.Y,<X+1.0`) instead of open-ended `>=X.Y.Z`.

**Why:** Prevents a future `docker build` from pulling a breaking or compromised major version.

---

## macOS Keychain Integration

The `make save-password` command stores your password/token in the macOS Keychain instead of writing plaintext to `~/.zshrc`.

```bash
# Save
make -f vault/Makefile save-password

# Load
export VAULT_PASSWORD=$(security find-generic-password -a jogi-vault -s JogiVault -w)
```

**Why:** Plaintext passwords in shell config files are readable by any process running as your user.
