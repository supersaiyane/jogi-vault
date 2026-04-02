# Troubleshooting

## "Wrong password or vault file is corrupted"

- Double-check your password (case-sensitive)
- If using a machine token, verify `vault.token` file exists in `vault/data/`
- If vault is truly corrupted, restore from Google Drive backup

## "TOTP code required"

- Enter the 6-digit code from your authenticator app
- Or enter your emergency key (`EMRG-...`) in the TOTP field
- Make sure your phone's clock is accurate (TOTP is time-based)

## "Too many login attempts"

- Wait 5 minutes and try again
- Rate limit: 5 attempts per 5 minutes per IP address

## "Invalid or expired machine token"

- The machine token may have been revoked
- The `vault.token` file may be missing or moved
- Generate a new token: API tab → Generate Machine Token

## Vault UI won't start

- Check port 5111 is not in use: `lsof -i :5111`
- Check Python version: `python --version` (need 3.11+)
- Check dependencies: `pip install flask cryptography pyotp`

## Google Drive backup fails

- Verify OAuth credentials in Backup tab
- Re-authorize: Disconnect → reconnect Google Drive
- Check internet connection
- Verify Gmail App Password is correct (not your real Gmail password)

## Can't restore from backup

- Email verification must be configured first
- Check your inbox (and spam folder) for the verification code
- The code expires after 10 minutes — request a new one

## Namespace data inaccessible after password change

- This bug was fixed in v2.0
- Password change now re-encrypts ALL namespaces
- If you hit this on an older version, restore from backup

## CSRF error / "Invalid request"

- Your session may have expired — go back and try again
- Clear browser cookies for localhost:5111 and re-login
- This can happen if you have multiple vault tabs open

## Docker container won't start

- Check logs: `docker-compose logs vault-ui`
- Verify `vault/data/` directory exists and is writable
- Check `VAULT_PASSWORD` env var is set correctly in `.env`

## "API not enabled" from REST API

- Generate an API token from the web UI (API tab)
- Make sure `VAULT_PASSWORD` is set in the vault-ui container environment
- Check the vault UI is running and healthy
