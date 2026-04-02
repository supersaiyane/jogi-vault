# Operational Flows

Step-by-step diagrams for every major vault operation.

---

## Encryption Flow

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
AES-256-GCM ENCRYPT
      │
      ▼
vault/data/vault.enc ─── safe to commit
```

To decrypt: Same password + same salt → same key → decrypt vault.enc

---

## Login Flow

```
User enters: password + 6-digit TOTP code
      │
      ▼
Rate limit check (max 5 attempts / 5 min per IP)
      │
      ├── Too many attempts → "Please wait" error
      │
      ▼
Password check:
   PBKDF2(password, salt) → key → decrypt vault.enc
      │
      ├── Wrong password → error
      │
      ▼
TOTP check:
   Decrypt vault.totp → TOTP secret
   Verify code (±1 window tolerance)
      │
      ├── Wrong code → error
      ├── EMRG-... entered → Emergency key flow
      │
      ▼
SUCCESS → encrypted session → dashboard
```

---

## Secret CRUD Flow

### Create / Update

```
v.set("KEY", "value")
      │
      ▼
_load() → decrypt vault.enc → get data dict
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

### Read

```
vault.get("KEY")
      │
      ▼
Check memory cache → found? → return instantly
      │ (miss)
      ▼
_load() → decrypt vault.enc → cache → return value
```

### Delete

```
v.delete("KEY")
      │
      ▼
_load() → del data["KEY"] → del data["__expiry_KEY__"]
      │
      ▼
_save(data) → encrypt → write
      │
      ▼
Audit log: {"action":"delete","key":"KEY"}
```

---

## Namespace Flow

### Create

```
create_namespace("payments")
      │
      ▼
Validate name → check doesn't exist
      │
      ▼
Random salt → vault-payments.salt
PBKDF2(password, salt) → key
AES-256-GCM({}) → vault-payments.enc
```

### Delete

```
delete_namespace("payments")
      │
      ▼
Delete vault-payments.enc + vault-payments.salt
→ ALL SECRETS IN THIS NAMESPACE GONE FOREVER
```

---

## Password Change Flow

```
make change-password
      │
      ▼
Step 1: Load ALL namespace data with old key
   vault.enc, vault-payments.enc, etc.
      │
      ▼
Step 2: Read TOTP secret with old key
      │
      ▼
Step 3: Read recovery key with old key
      │
      ▼
Step 4: Revoke machine token
      │
      ▼
Step 5: For EACH namespace:
   New random salt → PBKDF2(new_password) → re-encrypt
      │
      ▼
Step 6: Re-encrypt TOTP with new key
      │
      ▼
Step 7: Re-create recovery bundle
      │
      ▼
Done → generate new machine token
```

---

## Machine Token Flow

```
GENERATE:
   random VLT-... → PBKDF2 → Fernet key
   → encrypt(real_password) → vault.token

USE:
   VLT-... → PBKDF2 → Fernet key
   → decrypt(vault.token) → real password
   → PBKDF2(password, salt) → AES key → unlock vault

REVOKE:
   delete vault.token → instant invalidation
```

---

## Backup Flow

```
Trigger: manual button OR auto-schedule
      │
      ▼
Zip vault/data/ (except backup-oauth.json)
      │
      ▼
OAuth2 → Google Drive → upload zip
      │
      ▼
Prune: keep 10 most recent
```

## Restore Flow

```
Click "Restore" → enter email → send 6-digit code
      │
      ▼
Enter code → verify (constant-time compare)
      │
      ▼
Download zip → validate paths (traversal check)
      │
      ▼
Extract to vault/data/ → done
```

---

## Emergency Key Flow

```
Enter EMRG-XXXXX-XXXXX-XXXXX-XXXXX in TOTP field
      │
      ▼
PBKDF2(key) → compare to stored hash
      │
      ├── Wrong → error
      │
      ▼
Old key consumed → NEW key generated → shown once
      │
      ▼
SAVE THE NEW KEY → enter vault
```

---

## Recovery Key Flow

```
Enter JOGI-XXXXX-XXXXX-XXXXX-XXXXX
      │
      ▼
PBKDF2(recovery_key) → decrypt recovery bundle
      │
      ▼
Reveals OLD password → full password change
      │
      ▼
Done → generate new machine token
```

---

## REST API Flow

```
GET /api/v1/secret/KEY
Authorization: Bearer TOKEN
      │
      ▼
Validate token (constant-time)
      │
      ├── Invalid → 401
      │
      ▼
Decrypt vault → get key
      │
      ├── Not found → 404
      │
      ▼
200: {"key":"KEY","value":"...","namespace":"default"}
```

---

## Docker Flow

```
docker-compose up -d
      │
      ▼
Build image (Dockerfile)
   python:3.11-slim → pip install → copy 4 files
      │
      ▼
Mount ./vault/data → /app/vault/data
      │
      ▼
VAULT_PASSWORD=VLT-... → pre-unlocks API
      │
      ▼
Flask → http://localhost:5111
```

---

## See Also

- [Encryption & Crypto](Encryption-&-Crypto) — how AES-256-GCM and PBKDF2 work
- [Authentication](Authentication) — login, TOTP, emergency/recovery keys
- [Secret Management](Secret-Management) — CRUD with code examples
- [Backup & Restore](Backup-&-Restore) — Google Drive setup
