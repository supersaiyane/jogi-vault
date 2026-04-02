# Web UI

Full-featured browser interface at `http://localhost:5111`.

## Tabs

### Secrets Tab
- View all secrets (values hidden by default)
- Show/Hide individual values
- Add, edit, delete secrets
- Filter by tag/type
- Namespace selector in navigation bar

### Backup Tab
- Google Drive connection (OAuth2)
- Email verification configuration
- Auto-backup schedule (1–24 hours)
- Manual "Backup Now" button
- Backup history with restore buttons

### API Tab
- Machine token generation / rotation / revocation
- REST API token generation
- Code examples (Python, curl)
- Namespace management (create, delete, list)

## Login

1. Enter master password
2. Enter 6-digit TOTP code (or emergency key)
3. Click "Unlock"

Rate limiting: 5 attempts per 5 minutes per IP.

## Identity Guard

Editing or deleting a secret requires re-entering your password + TOTP code, even while logged in. This prevents damage from session hijacking or an unlocked browser.

## Locking

Click "Lock" in the top-right to clear your session and return to login.

## Starting the UI

```bash
# Local Python
make -f vault/Makefile up

# Docker
docker-compose up vault-ui -d

# Standalone Docker
cd vault/ && docker-compose up -d
```
