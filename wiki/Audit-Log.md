# Audit Log

Every security-relevant operation is logged to an append-only file.

## Location

```
vault/data/audit.log
```

## Format

One JSON object per line:

```json
{"ts":"2026-04-02T10:30:00+00:00","action":"login","key":"","ns":"default","ok":true,"detail":""}
{"ts":"2026-04-02T10:30:05+00:00","action":"set","key":"API_KEY","ns":"jogiexplains-yt","ok":true,"detail":""}
{"ts":"2026-04-02T10:31:00+00:00","action":"login","key":"","ns":"default","ok":false,"detail":"wrong TOTP code"}
```

## Logged Actions

| Action | Description |
|--------|-------------|
| `login` | Successful interactive login |
| `login` (ok:false) | Failed login (wrong password, TOTP, emergency key) |
| `set` | Secret created or updated |
| `delete` | Secret deleted |
| `import_env` | Bulk import from .env file |
| `setup_totp` | TOTP 2FA enabled |
| `disable_totp` | TOTP 2FA disabled |
| `rotate_emergency_key` | New emergency key generated |
| `emergency_key_used` | Emergency key consumed for login |
| `generate_machine_token` | Machine token created |
| `revoke_machine_token` | Machine token revoked |
| `change_password` | Master password changed |
| `reset_password` | Password reset via recovery key |
| `init_recovery_key` | Recovery key created |
| `create_namespace` | New namespace created |
| `delete_namespace` | Namespace deleted |

## Viewing the Log

**CLI:**
```bash
make -f vault/Makefile audit              # last 20 entries (formatted)
make -f vault/Makefile audit-failures     # only failed operations
```

**Shell:**
```bash
# Last 20 entries (formatted)
tail -20 vault/data/audit.log | python -m json.tool

# Find all failed logins
grep '"ok":false' vault/data/audit.log

# Find all operations on a specific key
grep 'ANTHROPIC_API_KEY' vault/data/audit.log

# Find all deletes
grep '"action":"delete"' vault/data/audit.log

# Count by action type
cat vault/data/audit.log | python -c "
import json, sys, collections
c = collections.Counter()
for line in sys.stdin:
    c[json.loads(line)['action']] += 1
for k, v in c.most_common():
    print(f'  {v:4d}  {k}')
"
```

## Design Principles

- **Append-only** — entries are never modified or deleted
- **Non-blocking** — if logging fails (disk full, permissions), the vault operation still completes normally
- **No secrets logged** — only key names, never values
- **Timestamped** — UTC ISO-8601 format
