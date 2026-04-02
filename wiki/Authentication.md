# Authentication

## Authentication Factors

| Factor | Type | When Used |
|--------|------|-----------|
| Master password | Something you know | Every login |
| TOTP code | Something you have | Every login (if enabled) |
| Emergency key (EMRG-...) | Something you have | TOTP bypass (one-time) |
| Recovery key (JOGI-...) | Something you have | Password reset |
| Machine token (VLT-...) | Something you have | Automated access |
| API token | Something you have | REST API access |

---

## Login Flow

```
User enters: password + 6-digit TOTP code
      │
      ▼
Rate limit check (max 5 attempts / 5 minutes per IP)
      │
      ├── Too many attempts → "Please wait" error
      │
      ▼
Password check:
   PBKDF2(password, salt) → key → decrypt vault.enc
      │
      ├── Wrong password → "Wrong password" error
      │
      ▼
TOTP check:
   Decrypt vault.totp → get TOTP secret
   Verify 6-digit code matches current time window
      │
      ├── Wrong code → "Wrong authenticator code" error
      ├── EMRG-... entered → Emergency key flow
      │
      ▼
SUCCESS → encrypted session → redirect to dashboard
```

---

## TOTP Two-Factor Authentication

Works with YubiKey, Google Authenticator, Microsoft Authenticator, Authy, 1Password, or any TOTP app.

**Setup:** Scan QR code → enter 6-digit code to confirm

**Login:** Enter the current 6-digit code from your app

**How it works:**
1. Random TOTP secret generated during setup (Base32 encoded)
2. Secret encrypted with AES-256-GCM → `vault.totp`
3. On login: decrypt secret → `TOTP(secret, current_time)` → expected code
4. Compare user code vs expected (±1 window = accepts previous code too)

**Commands:**
```bash
make -f vault/Makefile setup-totp P=xxx      # enable
make -f vault/Makefile disable-totp P=xxx    # disable
```

---

## Emergency Key

**Format:** `EMRG-XXXXX-XXXXX-XXXXX-XXXXX`

Use when you lose access to your authenticator app.

```
1. At login, enter password as normal
2. In the TOTP field, paste: EMRG-XXXXX-XXXXX-XXXXX-XXXXX
      │
      ▼
3. Server detects "EMRG-" prefix → emergency flow
      │
      ▼
4. PBKDF2(entered_key) compared to stored hash
   (constant-time comparison)
      │
      ├── Wrong key → error
      │
      ▼
5. Key consumed (old hash deleted)
      │
      ▼
6. NEW emergency key generated and displayed
      │
      ▼
7. SAVE THE NEW KEY IMMEDIATELY
```

**Why single-use?** If someone found your emergency key, they could only use it once. After that, a new key is generated that only you can see.

```bash
make -f vault/Makefile new-emergency-key P=xxx   # rotate manually
```

---

## Recovery Key

**Format:** `JOGI-XXXXX-XXXXX-XXXXX-XXXXX`

Resets your master password when you forget it.

```
1. Enter recovery key: JOGI-XXXXX-XXXXX-XXXXX-XXXXX
      │
      ▼
2. PBKDF2(recovery_key, bundle_salt) → bundle_key
      │
      ▼
3. Decrypt bundle → reveals OLD password
      │
      ▼
4. Use old password to decrypt everything
      │
      ▼
5. Re-encrypt everything with new password
```

> The recovery key does NOT bypass TOTP. You still need your authenticator or emergency key.

```bash
make -f vault/Makefile forgot-password    # interactive reset
```

---

## Security Model Summary

```
Normal login        →  password  +  TOTP code
Lost authenticator  →  password  +  Emergency key (EMRG-...)
Forgot password     →  Recovery key (JOGI-...)
Automated access    →  Machine token (VLT-...) in VAULT_PASSWORD
API access          →  REST API token in Authorization: Bearer header
Vault corrupted     →  Restore from Google Drive backup (email-verified)
```

---

## See Also
- [Machine Tokens](Machine-Tokens) — automated access without passwords
- [Security Features](Security-Features) — CSRF, rate limiting, session encryption
