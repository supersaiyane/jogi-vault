# Jogi Vault Wiki

A self-contained encrypted secret manager with AES-256-GCM encryption, TOTP 2FA, and a web UI.

---

## Quick Navigation

### At a Glance
- **[Features](Features) — complete one-shot overview of everything Jogi Vault can do**

### Getting Started
- [Installation & Setup](Installation-&-Setup) — first-time setup, prerequisites, Docker
- [Quick Start Guide](Quick-Start-Guide) — get running in 5 minutes

### Core Features
- [Secret Management](Secret-Management) — create, read, update, delete secrets
- [Namespaces](Namespaces) — isolate secrets by project or environment
- [Secret Expiry](Secret-Expiry) — TTL and rotation tracking

### Security
- [Encryption & Crypto](Encryption-&-Crypto) — AES-256-GCM, PBKDF2, key derivation
- [Authentication](Authentication) — password, TOTP, emergency key, recovery key
- [Machine Tokens](Machine-Tokens) — VLT-... tokens for automated access
- [Audit Log](Audit-Log) — append-only security event log
- [Security Features](Security-Features) — CSRF, rate limiting, session encryption

### Access Methods
- [Web UI](Web-UI) — browser-based interface at localhost:5111
- [CLI & Makefile](CLI-&-Makefile) — command-line operations
- [REST API](REST-API) — HTTP endpoints for any language
- [Python Client](Python-Client) — VaultClient and VaultHTTPClient

### Operations
- [Backup & Restore](Backup-&-Restore) — Google Drive backup with email verification
- [Password Management](Password-Management) — change, reset, keychain storage
- [Docker Deployment](Docker-Deployment) — standalone and full pipeline compose files

### Reference
- [Operational Flows](Operational-Flows) — step-by-step diagrams for every operation
- [File Reference](File-Reference) — every file in vault/data/ explained
- [Troubleshooting](Troubleshooting) — common problems and fixes
- [Security Best Practices](Security-Best-Practices) — do's and don'ts

---

## Architecture Overview

```
vault/
├── ui.py              Web UI (Flask, port 5111)
├── cli.py             Command-line interface
├── backup.py          Google Drive backup manager
├── Dockerfile         Container definition
├── Makefile           Convenience targets
├── docker-compose.yml Standalone compose file
├── wiki/              This wiki
└── data/
    ├── vault.enc           Encrypted secrets (AES-256-GCM)
    ├── vault.salt          Password derivation salt
    ├── vault.totp          Encrypted TOTP secret
    ├── vault.recovery      Recovery key bundle
    ├── vault.emergency     Emergency key hash
    ├── vault.token         Machine token bundle
    └── audit.log           Security audit log
```

## Pipeline Flow

```
Password → PBKDF2 (480K rounds) → 32-byte key → AES-256-GCM → vault.enc
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Encryption | AES-256-GCM via `cryptography` library |
| Key derivation | PBKDF2-SHA256, 480,000 iterations |
| 2FA | TOTP (RFC 6238) via `pyotp` |
| Web UI | Flask |
| CLI output | Rich |
| Backup | Google Drive API |
| Container | Docker + docker-compose |
