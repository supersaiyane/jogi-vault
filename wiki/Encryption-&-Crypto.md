# Encryption & Crypto

## Overview

```
YOUR PASSWORD ─── "mysecretpassword123"
      │
      ▼
PBKDF2-SHA256 (480,000 rounds + random salt)
      │
      ▼
32-BYTE KEY ─── 0xA7F3...2B1C
      │
      ▼
AES-256-GCM ENCRYPT ─── your secrets become unreadable bytes
      │
      ▼
vault/data/vault.enc ─── safe to commit to git
```

---

## AES-256-GCM

All secrets are encrypted with **AES-256-GCM** (Galois/Counter Mode) — the gold standard for authenticated encryption.

| Property | Value |
|----------|-------|
| Algorithm | AES-256 |
| Mode | GCM (Galois/Counter Mode) |
| Key size | 256 bits (32 bytes) |
| Nonce size | 96 bits (12 bytes, random per operation) |
| Authentication | Built-in GCM auth tag (detects tampering) |
| Library | `cryptography.hazmat.primitives.ciphers.aead.AESGCM` |

### Encrypted Data Format

```
JV01 (4 bytes magic prefix) + nonce (12 bytes) + ciphertext + auth tag
```

The `JV01` magic prefix identifies AES-256-GCM format vs legacy Fernet.

### Why GCM?

- **Authenticated:** tamper detection built in (no separate HMAC needed)
- **Fast:** hardware-accelerated on modern CPUs (AES-NI)
- **Standard:** used by TLS 1.3, Google, AWS, Signal

---

## PBKDF2-SHA256 Key Derivation

Your master password is never used directly as an encryption key.

```
Password: "mysecretpassword123"
Salt:     0x7A3F... (random 16 bytes, stored in vault.salt)
Iterations: 480,000
Output:   32-byte key for AES-256-GCM
```

| Property | Value |
|----------|-------|
| Algorithm | PBKDF2 |
| Hash | SHA-256 |
| Iterations | 480,000 |
| Salt | 16 bytes (random, per namespace) |
| Output | 32 bytes (256 bits) |

### Why 480,000 iterations?

OWASP recommends a minimum of 600,000 for PBKDF2-SHA256 (as of 2023). 480,000 provides strong brute-force resistance while keeping unlock time under 1 second on modern hardware.

### Why per-namespace salt?

Each namespace has its own random salt. Even with the same password, different namespaces produce different encryption keys. This means:
- Compromising one namespace's key doesn't compromise others
- You can't tell if two namespaces use the same password

---

## Legacy Migration (Fernet → AES-256-GCM)

The vault originally used Fernet (AES-128-CBC + HMAC-SHA256). The upgrade to AES-256-GCM is **transparent and automatic:**

1. **Reading:** `_decrypt_bytes()` checks the first 4 bytes
   - Starts with `JV01` → AES-256-GCM
   - Otherwise → legacy Fernet fallback
2. **Writing:** `_save()` always writes AES-256-GCM format
3. **Migration:** happens automatically on the first write after upgrade

No manual steps needed. No data loss. No downtime.

### Why Fernet was replaced

| | Fernet | AES-256-GCM |
|---|---|---|
| AES key size | 128 bits | 256 bits |
| Mode | CBC | GCM |
| Auth | Separate HMAC-SHA256 | Built-in GCM tag |
| Nonce/IV | 128-bit random IV | 96-bit random nonce |
| Standard | Custom (PyCA) | NIST standard |

---

## What's Encrypted With What

| File | Encryption | Key Source |
|------|-----------|-----------|
| `vault.enc` | AES-256-GCM | PBKDF2(password, vault.salt) |
| `vault-<ns>.enc` | AES-256-GCM | PBKDF2(password, vault-<ns>.salt) |
| `vault.totp` | AES-256-GCM | Same key as vault.enc |
| `vault.recovery` | AES-256 (Fernet) | PBKDF2(recovery_key, bundle_salt) |
| `vault.token` | AES-256 (Fernet) | PBKDF2(machine_token, token_salt) |
| `vault.emergency` | PBKDF2 hash only | Not reversible |
| `vault.salt` | Not encrypted | Just a random salt |
| `audit.log` | Not encrypted | Plaintext JSON lines |

---

## Security Properties

- **Confidentiality:** AES-256-GCM — cannot read without the key
- **Integrity:** GCM auth tag — cannot modify without detection
- **Key derivation:** PBKDF2 — cannot brute-force the password easily
- **Salt:** random per namespace — cannot use rainbow tables
- **Nonce:** random per write — same plaintext produces different ciphertext
- **Password:** never stored — only exists in RAM during a session
