# CLI & Makefile

## Makefile Targets

All targets run from the project root or inside `vault/`:
```bash
make -f vault/Makefile <target>    # from project root
make <target>                      # from inside vault/
```

Set `VAULT_PASSWORD` in your environment or pass `P=xxx`.

### UI

| Target | Description |
|--------|-------------|
| `up` | Start vault UI locally → http://localhost:5111 |
| `docker-up` | Start via docker-compose (detached) |
| `docker-build` | Rebuild Docker image + restart |
| `docker-down` | Stop the vault container |
| `docker-logs` | Tail live logs |

### Secrets

| Target | Usage |
|--------|-------|
| `list` | `make list P=xxx` |
| `set` | `make set P=xxx K=MY_KEY V=my_value` |
| `get` | `make get P=xxx K=MY_KEY` |
| `delete` | `make delete P=xxx K=MY_KEY` |
| `import-env` | `make import-env P=xxx` |

### Namespaces

| Target | Usage |
|--------|-------|
| `namespaces` | `make namespaces` |
| `new-namespace` | `make new-namespace P=xxx NS=my-project` |
| `delete-namespace` | `make delete-namespace P=xxx NS=my-project` |

### Password & 2FA

| Target | Usage |
|--------|-------|
| `change-password` | `make change-password` (interactive) |
| `forgot-password` | `make forgot-password` (interactive) |
| `save-password` | `make save-password` (macOS Keychain) |
| `load-password` | `make load-password` (shows shell command) |
| `setup-totp` | `make setup-totp P=xxx` |
| `disable-totp` | `make disable-totp P=xxx` |
| `new-emergency-key` | `make new-emergency-key P=xxx` |

### Machine Token

| Target | Usage |
|--------|-------|
| `generate-token` | `make generate-token P=real_password` |
| `revoke-token` | `make revoke-token P=xxx` |

### Backup

| Target | Usage |
|--------|-------|
| `backup` | `make backup P=xxx` |

### Expiry

| Target | Usage |
|--------|-------|
| `set-expiry` | `make set-expiry P=xxx K=KEY V=value E=2026-12-31` |
| `expiring` | `make expiring P=xxx DAYS=30` |

### Audit

| Target | Usage |
|--------|-------|
| `audit` | `make audit` (last 20 entries) |
| `audit-failures` | `make audit-failures` (failed ops only) |

### Status

| Target | Usage |
|--------|-------|
| `status` | `make status` (health check) |
| `help` | `make help` (list all targets) |

---

## CLI (vault/cli.py)

Direct Python CLI without Makefile:

```bash
cd jogi-explains/
PYTHONPATH=. VAULT_PASSWORD=xxx python vault/cli.py <command>
```

| Command | Description |
|---------|-------------|
| `init` | Create vault + QR + emergency key |
| `setup-totp` | Re-setup / replace TOTP |
| `disable-totp` | Remove TOTP requirement |
| `set KEY VALUE` | Add or update a secret |
| `get KEY` | Retrieve a secret |
| `list` | List all key names |
| `delete KEY` | Remove a secret |
| `import-env [file]` | Import from .env file |
| `export-env` | Print keys (values masked) |
| `change-password` | Change master password |
| `forgot-password` | Reset via recovery key |
| `new-emergency-key` | Rotate emergency key |

---

## Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `P` | Password or VLT-... token | `P=xxx` |
| `K` | Key name | `K=ANTHROPIC_API_KEY` |
| `V` | Key value | `V=sk-ant-api03-xxx` |
| `NS` | Namespace | `NS=payments` |
| `E` | Expiry date | `E=2026-12-31` |
| `DAYS` | Days for expiry check | `DAYS=30` |
