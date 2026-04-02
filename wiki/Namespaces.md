# Namespaces

A namespace is a separate encrypted key store. All namespaces share the same master password but have completely isolated secrets.

## Use Cases

- Separate keys per project (`jogiexplains-yt`, `jogi-bhakti`)
- Separate by environment (`production`, `staging`, `development`)
- Separate by team or service

## How It Works

Each namespace gets its own encrypted files:

```
vault/data/vault.enc              → default namespace
vault/data/vault-payments.enc     → "payments" namespace
vault/data/vault-staging.enc      → "staging" namespace
vault/data/vault-payments.salt    → "payments" salt
vault/data/vault-staging.salt     → "staging" salt
```

Shared across all namespaces:
- Same master password
- Same TOTP 2FA
- Same recovery / emergency keys

---

## Create a Namespace

**Web UI:** Click "+ NS" in the top navigation → enter name → Create

**CLI:**
```bash
make -f vault/Makefile new-namespace P=xxx NS=my-project
```

### Naming Rules
- Lowercase only
- Alphanumeric characters and hyphens
- `default` is reserved
- Examples: `payments`, `staging`, `jogiexplains-yt`, `jogi-bhakti`

### What Happens Internally

```
create_namespace("my-project")
    │
    ▼
Validate name (lowercase, alphanumeric + hyphens)
    │
    ▼
Check: vault-my-project.enc doesn't exist yet
    │
    ▼
Generate random salt → vault-my-project.salt
PBKDF2(password, salt) → namespace-specific key
AES-256-GCM encrypt {} → vault-my-project.enc
```

---

## Switch Namespace

**Web UI:** Use the dropdown in the top navigation bar. The Secrets tab updates to show keys from the selected namespace.

**Python:**
```python
vault.get("KEY", ns="my-project")
vault.all(ns="my-project")
vault.keys(ns="my-project")
```

**REST API:**
```bash
curl "http://localhost:5111/api/v1/secret/STRIPE_KEY?ns=payments" \
     -H "Authorization: Bearer TOKEN"
```

---

## Delete a Namespace

**Web UI:** API tab → Namespaces table → click "Delete" → confirm

**CLI:**
```bash
make -f vault/Makefile delete-namespace P=xxx NS=my-project
```

> **WARNING:** Deleting a namespace permanently removes ALL its secrets and the encrypted file. This cannot be undone unless you have a backup.

---

## List All Namespaces

**CLI:**
```bash
make -f vault/Makefile namespaces
```

**Python:**
```python
vault.namespaces()  # → ["default", "payments", "my-project"]
```

**REST API:**
```bash
curl http://localhost:5111/api/v1/namespaces \
     -H "Authorization: Bearer TOKEN"
```

---

## Multi-Channel Example (Jogi Brand)

```bash
# One vault, four channels
make -f vault/Makefile new-namespace P=xxx NS=jogiexplains-yt
make -f vault/Makefile new-namespace P=xxx NS=jogi-bhakti
make -f vault/Makefile new-namespace P=xxx NS=jogi-kids
make -f vault/Makefile new-namespace P=xxx NS=jogi-motivates
```

```python
# In code — just swap namespace
from src.vault_client import vault

explains_key = vault.get("YOUTUBE_API_KEY", ns="jogiexplains-yt")
bhakti_key   = vault.get("YOUTUBE_API_KEY", ns="jogi-bhakti")
```

```yaml
# In docker-compose — one env var per channel
environment:
  - VAULT_NAMESPACE=jogiexplains-yt
```
