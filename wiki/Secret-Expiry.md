# Secret Expiry

Secrets can have an optional expiry timestamp to track when API keys need rotation.

## Set a Secret with Expiry

**CLI:**
```bash
make -f vault/Makefile set-expiry P=xxx K=STRIPE_KEY V=sk_live_xxx E=2026-12-31
```

**Python:**
```python
vault.set_with_expiry(
    "STRIPE_KEY",
    "sk_live_xxxxx",
    "2026-12-31T00:00:00+00:00"
)
```

## Check Expiry

```python
vault.get_expiry("STRIPE_KEY")
# → "2026-12-31T00:00:00+00:00"

vault.is_expired("STRIPE_KEY")
# → True/False
```

## List Expiring Secrets

**CLI:**
```bash
make -f vault/Makefile expiring P=xxx              # within 30 days (default)
make -f vault/Makefile expiring P=xxx DAYS=7       # within 7 days
make -f vault/Makefile expiring P=xxx DAYS=90      # within 90 days
```

**Python:**
```python
vault.list_expiring(within_days=30)
# → [("STRIPE_KEY", "2026-12-31T00:00:00+00:00")]
```

## How It Works

```
set_with_expiry("STRIPE_KEY", "sk_live_xxx", "2026-12-31T00:00:00+00:00")
      │
      ▼
Stored as two entries in the encrypted vault:
   data["STRIPE_KEY"] = "sk_live_xxx"
   data["__expiry_STRIPE_KEY__"] = "2026-12-31T00:00:00+00:00"
```

## Important Notes

- **Expiry is advisory** — expired keys still return values
- This prevents your pipeline from breaking while you rotate keys
- Expiry timestamps must be ISO-8601 format with timezone
- Deleting a key automatically removes its expiry metadata
- Expiry metadata is stored encrypted alongside the secret
