# Password Management

## Change Master Password

```bash
make -f vault/Makefile change-password
```

Prompts for: current password → new password → confirm

### What happens internally

```
Step 1: Load ALL namespace data with old key
   vault.enc, vault-payments.enc, etc. → decrypt → save in memory

Step 2: Read TOTP secret with old key
   vault.totp → decrypt → save in memory

Step 3: Read recovery key with old key

Step 4: Revoke machine token (vault.token deleted)

Step 5: For EACH namespace:
   Generate new random salt → write to .salt file
   PBKDF2(new_password, new_salt) → new key
   AES-256-GCM encrypt data → write to .enc file

Step 6: Re-encrypt TOTP secret with new key

Step 7: Re-create recovery bundle with new password

Step 8: Re-encrypt recovery key in vault data with new key
```

### After changing password

1. **Generate a new machine token** (old one was revoked)
2. **Update `VAULT_PASSWORD` everywhere** (docker-compose, .env, CI/CD)

---

## Forgot Password — Reset with Recovery Key

```bash
make -f vault/Makefile forgot-password
```

Prompts for: recovery key (`JOGI-...`) → new password → confirm

### How it works

```
1. Read vault.recovery file
2. PBKDF2(recovery_key, bundle_salt) → bundle_key
3. Decrypt bundle → reveals OLD password
4. Use old password to decrypt everything
5. Full password change with new password
```

> The recovery key does NOT bypass TOTP. You still need your authenticator or emergency key.

---

## Save Password to macOS Keychain

```bash
# Save
make -f vault/Makefile save-password

# Show the load command
make -f vault/Makefile load-password

# Load into current shell
export VAULT_PASSWORD=$(security find-generic-password -a jogi-vault -s JogiVault -w)
```

This stores your password/token in the macOS Keychain under "JogiVault" instead of writing plaintext to `~/.zshrc`.
