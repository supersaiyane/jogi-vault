# REST API

HTTP endpoints for reading secrets from any language or service.

## Prerequisites

1. Vault UI must be running
2. Generate an API token (API tab → "Generate API Token")
3. Set `VAULT_PASSWORD` env var on the vault-ui process (for auto-unlock)

---

## Endpoints

### Get a single secret

```
GET /api/v1/secret/<KEY>
GET /api/v1/secret/<KEY>?ns=<namespace>
```

**Response (200):**
```json
{
  "key": "ANTHROPIC_API_KEY",
  "value": "sk-ant-api03-xxxxx",
  "namespace": "default"
}
```

### List all key names

```
GET /api/v1/secrets
GET /api/v1/secrets?ns=<namespace>
```

**Response (200):**
```json
{
  "keys": ["ANTHROPIC_API_KEY", "ELEVENLABS_KEY"],
  "namespace": "default",
  "count": 2
}
```

### List all namespaces

```
GET /api/v1/namespaces
```

**Response (200):**
```json
{
  "namespaces": ["default", "payments", "staging"]
}
```

---

## Authentication

All requests require the `Authorization` header:

```
Authorization: Bearer YOUR_API_TOKEN
```

---

## Error Responses

| Code | Meaning | Example |
|------|---------|---------|
| 401 | Missing or invalid token | `{"error": "Invalid token"}` |
| 404 | Key not found | `{"error": "Key 'XXX' not found in namespace 'default'"}` |
| 503 | Vault locked | `{"error": "Vault is locked. Login to the UI or set VAULT_PASSWORD env var."}` |

---

## Examples

### curl

```bash
# Get a secret
curl http://localhost:5111/api/v1/secret/ANTHROPIC_API_KEY \
     -H "Authorization: Bearer YOUR_TOKEN"

# From a namespace
curl "http://localhost:5111/api/v1/secret/STRIPE_KEY?ns=payments" \
     -H "Authorization: Bearer YOUR_TOKEN"

# List all keys
curl http://localhost:5111/api/v1/secrets \
     -H "Authorization: Bearer YOUR_TOKEN"

# List namespaces
curl http://localhost:5111/api/v1/namespaces \
     -H "Authorization: Bearer YOUR_TOKEN"
```

### JavaScript / Node.js

```js
const VAULT = "http://localhost:5111/api/v1";
const TOKEN = process.env.VAULT_API_TOKEN;

async function getSecret(key, ns = "default") {
  const r = await fetch(`${VAULT}/secret/${key}?ns=${ns}`, {
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  const { value } = await r.json();
  return value;
}

const apiKey = await getSecret("ANTHROPIC_API_KEY");
const stripe = await getSecret("STRIPE_KEY", "payments");
```

### Python (requests)

```python
import requests

VAULT = "http://localhost:5111/api/v1"
TOKEN = "YOUR_API_TOKEN"

def get_secret(key, ns="default"):
    r = requests.get(
        f"{VAULT}/secret/{key}",
        params={"ns": ns},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    return r.json()["value"]

api_key = get_secret("ANTHROPIC_API_KEY")
```

---

## Request Flow

```
Your app sends:
   GET /api/v1/secret/ANTHROPIC_API_KEY
   Authorization: Bearer abc123xyz
      │
      ▼
Flask receives request
      │
      ▼
@api_auth decorator:
   Extract token from "Bearer abc123xyz"
   Load stored token from vault (encrypted)
   secrets.compare_digest(sent, stored) — constant time
      │
      ├── No match → 401
      │
      ▼
Get VAULT_PASSWORD from app config
Create Vault instance
vault.get("ANTHROPIC_API_KEY")
      │
      ├── Key not found → 404
      │
      ▼
Return 200: {"key": "...", "value": "...", "namespace": "..."}
```
