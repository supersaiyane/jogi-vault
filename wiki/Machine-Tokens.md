# Machine Tokens

A machine token (`VLT-...`) hides your real password from config files and environment variables.

## How It Works

```
┌────────────┐     ┌─────────┐     ┌──────────────────┐
│ VLT-xxxxx  │────▶│ PBKDF2  │────▶│ Fernet key       │
│ (token)    │     │         │     │ Decrypt           │
└────────────┘     └─────────┘     │ vault.token file  │
                                    │      │            │
                                    │      ▼            │
                                    │ Real password     │
                                    │      │            │
                                    │      ▼            │
                                    │ PBKDF2 + salt     │
                                    │      │            │
                                    │      ▼            │
                                    │ AES-256 key       │
                                    │      │            │
                                    │      ▼            │
                                    │ Decrypt vault     │
                                    └──────────────────┘
```

**Defense in depth:**
- Attacker has `VLT-...` but no `vault.token` file → useless
- Attacker has `vault.token` but no `VLT-...` → useless
- Need **BOTH** to unlock

---

## Generate

**Web UI:** API tab → "Generate Machine Token" → copy `VLT-...` → save it

**CLI:**
```bash
make -f vault/Makefile generate-token P=your_real_password
```

Then set in your environment:
```bash
export VAULT_PASSWORD=VLT-xxxxxxxxxxxxxxxxxxx
```

Or in `.env`:
```
VAULT_PASSWORD=VLT-xxxxxxxxxxxxxxxxxxx
```

Or save to macOS Keychain:
```bash
make -f vault/Makefile save-password
```

---

## Revoke

**Web UI:** API tab → "Revoke" button

**CLI:**
```bash
make -f vault/Makefile revoke-token P=xxx
```

What happens: `vault.token` is deleted → all processes using `VLT-...` immediately fail. No password change needed.

---

## Rotate

**Web UI:** API tab → "Rotate Token"

Old token invalidated → new token generated → update `VAULT_PASSWORD` everywhere.

---

## Important Notes

- Changing your master password **auto-revokes** all machine tokens
- Only **one** machine token can be active at a time
- The token is useless without `vault/data/vault.token` on disk
- Generate a new token after every password change
