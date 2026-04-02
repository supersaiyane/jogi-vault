# Secret Management

## Create a Secret

**Web UI:**
1. Secrets tab → "+ Add key"
2. Key name: `ANTHROPIC_API_KEY` (auto-uppercased)
3. Value: `sk-ant-api03-xxxxx`
4. Type: API Key
5. Click "Save"

**CLI:**
```bash
make -f vault/Makefile set P=xxx K=ANTHROPIC_API_KEY V=sk-ant-api03-xxxxx
```

**Python:**
```python
from src.vault import Vault
v = Vault()
v.set("ANTHROPIC_API_KEY", "sk-ant-api03-xxxxx")
```

### How it works internally

```
v.set("KEY", "value")
    │
    ▼
_load() → decrypt vault.enc → get current data dict
    │
    ▼
data["KEY"] = "value"
    │
    ▼
_save(data) → AES-256-GCM encrypt → write vault.enc
    │
    ▼
Audit log: {"action":"set","key":"KEY"}
```

---

## Read a Secret

**Web UI:** Secrets tab → click "Show" to reveal, "Hide" to mask.

**CLI:**
```bash
make -f vault/Makefile get P=xxx K=ANTHROPIC_API_KEY
```

**Python:**
```python
from src.vault_client import vault

key = vault.get("ANTHROPIC_API_KEY")
# First call: decrypts from disk + caches in memory
# Subsequent calls: returns from memory instantly
```

---

## Update a Secret

**Web UI:**
1. Click "Edit" next to the key
2. Change the value and/or tag
3. Click "Update"
4. **Identity check:** re-enter password + TOTP code
5. Click "Confirm"

> The identity re-verification prevents unauthorized changes if someone accesses your browser while you're logged in.

**CLI:**
```bash
# Same command as create — it overwrites
make -f vault/Makefile set P=xxx K=ANTHROPIC_API_KEY V=new-value
```

---

## Delete a Secret

**Web UI:**
1. Click "Del" next to the key
2. Warning displayed: "You are about to permanently delete KEY"
3. **Identity check:** re-enter password + TOTP code
4. Click "Confirm"

**CLI:**
```bash
make -f vault/Makefile delete P=xxx K=ANTHROPIC_API_KEY
```

> Deletion is permanent. Recover from backup if needed.

---

## List All Secrets

**Web UI:** Secrets tab shows all keys. Use the type filter dropdown to narrow by category.

**CLI:**
```bash
make -f vault/Makefile list P=xxx
```

**Python:**
```python
names = vault.keys()                        # → ["ANTHROPIC_API_KEY", "ELEVENLABS_KEY", ...]
everything = vault.all()                    # → {"ANTHROPIC_API_KEY": "sk-...", ...}
many = vault.get_many("KEY1", "KEY2")       # → {"KEY1": "val1", "KEY2": "val2"}
```

**REST API:**
```bash
curl http://localhost:5111/api/v1/secrets \
     -H "Authorization: Bearer TOKEN"
```

---

## Bulk Import from .env

```bash
make -f vault/Makefile import-env P=xxx
```

This reads the `.env` file line by line:
- Skips empty lines, comments (`#`), lines without `=`
- Skips values containing `REPLACE_ME`
- Strips quotes from values
- Adds each `KEY=VALUE` to the vault

After import, you can delete the `.env` file — everything is safely encrypted.

---

## Key Tags / Types

Each secret can be tagged for visual organization in the web UI:

| Tag | Label | Color |
|-----|-------|-------|
| `api_key` | API Key | Blue |
| `password` | Password | Red |
| `rsa_private` | RSA Private Key | Dark Red |
| `rsa_public` | RSA Public Key | Green |
| `access_token` | Access Token | Yellow |
| `secret` | Secret | Purple |
| `url` | URL / Endpoint | Teal |
| `email` | Email | Gray |
| `certificate` | Certificate | Orange |
| `other` | Other | Dim |

Tags are stored as metadata inside the encrypted vault and can be filtered in the web UI.

---

## See Also
- [Namespaces](Namespaces) — isolate secrets by project
- [Secret Expiry](Secret-Expiry) — set TTL on secrets
- [REST API](REST-API) — access secrets over HTTP
