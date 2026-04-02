# File Reference

## Code Files

| File | Purpose |
|------|---------|
| `vault/ui.py` | Web UI (Flask, port 5111) |
| `vault/cli.py` | Command-line interface |
| `vault/backup.py` | Google Drive backup manager |
| `vault/Dockerfile` | Container definition |
| `vault/Makefile` | Convenience targets |
| `vault/docker-compose.yml` | Standalone compose file |
| `src/vault.py` | Core encryption engine |
| `src/vault_client.py` | VaultClient + VaultHTTPClient |

## Data Files (vault/data/)

| File | Encrypted? | Content | Safe to commit? |
|------|-----------|---------|----------------|
| `vault.enc` | AES-256-GCM | Encrypted secrets (default namespace) | Yes |
| `vault.salt` | No | Password derivation salt (16 bytes, base64) | Yes |
| `vault.totp` | AES-256-GCM | Encrypted TOTP secret | Yes |
| `vault.recovery` | AES-256 (Fernet) | Recovery key bundle | Yes |
| `vault.emergency` | PBKDF2 hash | Emergency key hash (not reversible) | Yes |
| `vault.token` | AES-256 (Fernet) | Machine token bundle | Yes |
| `audit.log` | No | Append-only security log (no secrets) | Yes |
| `backup-oauth.json` | No | Google Drive OAuth client creds | Yes |
| `vault-<ns>.enc` | AES-256-GCM | Namespace-specific secrets | Yes |
| `vault-<ns>.salt` | No | Namespace-specific salt | Yes |

## Documentation Files (vault/)

| File | Content |
|------|---------|
| `README.md` | Project documentation |
| `wiki/` | Full documentation wiki (23 markdown pages) |

## What NOT to commit

| Item | Why |
|------|-----|
| Your real password | Never stored anywhere |
| Recovery key plaintext | Store in password manager |
| Emergency key plaintext | Store in password manager |
| `.env` file | Contains VAULT_PASSWORD token |
