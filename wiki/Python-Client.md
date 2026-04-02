# Python Client

Two client classes for accessing secrets from Python code.

## VaultClient (Direct Mode — Recommended)

No HTTP. Reads encrypted files directly. Fastest method.

```python
from src.vault_client import vault   # module-level singleton

# Single key
api_key = vault.get("ANTHROPIC_API_KEY")

# Multiple keys → returns dict
keys = vault.get_many("ANTHROPIC_API_KEY", "ELEVENLABS_KEY", "PEXELS_KEY")

# From a specific namespace
stripe = vault.get("STRIPE_KEY", ns="payments")

# All key-value pairs
everything = vault.all()
everything = vault.all(ns="payments")

# Key names only (no values)
names = vault.keys()
names = vault.keys(ns="payments")

# List namespaces
spaces = vault.namespaces()

# Safe get (returns None if not found)
val = vault.get_or_none("MAYBE_EXISTS")

# Force re-read from disk
vault.clear_cache()
vault.clear_cache(ns="payments")
```

### How Caching Works

```
vault.get("KEY")
   │
   ▼
First call for this namespace?
   → Create Vault(password=env, namespace=default)
   → PBKDF2 → key → decrypt vault.enc → cache in memory
   → Return data["KEY"]

vault.get("KEY")  (second call)
   → Cached! Returns instantly from memory
```

### Custom Instance

```python
from src.vault_client import VaultClient

v = VaultClient(password="VLT-abc123", cache_values=False)
key = v.get("MY_KEY")
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `VAULT_PASSWORD` | Master password or VLT-... machine token |
| `VAULT_NAMESPACE` | Default namespace (used by `load_vault_into_env`) |

---

## VaultHTTPClient (HTTP Mode)

Talks to the REST API. Use when running in a separate service or non-Python language.

```python
from src.vault_client import VaultHTTPClient

http = VaultHTTPClient()   # reads VAULT_URL + VAULT_API_TOKEN from env

key = http.get("ANTHROPIC_API_KEY")
keys = http.get_many("ANTHROPIC_API_KEY", "ELEVENLABS_KEY")
all_keys = http.all(ns="payments")
names = http.keys()
spaces = http.namespaces()
http.clear_cache()
```

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VAULT_URL` | `http://localhost:5111` | Vault UI base URL |
| `VAULT_API_TOKEN` | (required) | REST API bearer token |

---

## When to Use Which

| Scenario | Use |
|----------|-----|
| Same Python project | `VaultClient` (direct) |
| Docker, same volume mounted | `VaultClient` (direct) |
| Separate service, same network | `VaultHTTPClient` (HTTP) |
| Different language (JS, Go, etc.) | REST API directly |
| CI/CD pipeline | Either, depending on setup |
