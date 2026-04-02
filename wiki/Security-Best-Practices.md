# Security Best Practices

## Do

- Use a strong master password (16+ characters)
- Enable TOTP two-factor authentication
- Save your recovery and emergency keys in a password manager
- Use machine tokens (`VLT-...`) instead of real passwords in config files
- Enable Google Drive backups
- Review the audit log periodically: `make -f vault/Makefile audit`
- Set expiry dates on API keys that rotate
- Revoke machine tokens you no longer need
- Change your password periodically
- Keep dependencies updated (`docker-compose up --build`)
- Use the macOS Keychain for password storage: `make save-password`

## Don't

- Don't write your real password in `.env`, `~/.zshrc`, or any file
- Don't share your recovery or emergency keys
- Don't commit `.env` files to git
- Don't disable TOTP unless you have a good reason
- Don't ignore expiry warnings on API keys
- Don't expose the vault UI to untrusted networks (keep on localhost)
- Don't delete `vault/data/` files without a backup
- Don't use the same password for the vault and other services
- Don't store the vault password in shell history (use `make save-password` instead)

## Incident Response

**If you suspect your password was compromised:**
1. Change password immediately: `make change-password`
2. Generate new machine token: `make generate-token P=new_password`
3. Update `VAULT_PASSWORD` everywhere
4. Check audit log for suspicious activity: `make audit-failures`
5. Rotate any API keys that may have been exposed

**If you suspect your machine token was compromised:**
1. Revoke immediately: `make revoke-token P=xxx`
2. Generate new token: `make generate-token P=xxx`
3. Update `VAULT_PASSWORD` everywhere
4. No password change needed (token is useless without `vault.token` file)

**If you lost your authenticator device:**
1. Use emergency key (`EMRG-...`) to log in
2. Save the new emergency key shown after login
3. Set up TOTP on new device: `make setup-totp P=xxx`
