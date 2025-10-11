# Persistent Settings Storage

Channel Identifiarr now stores settings persistently on the backend instead of browser localStorage.

## How It Works

- **Settings are stored** in `/data/settings.json` with restricted file permissions (600)
- **Credentials are kept** server-side for consistent access across browsers and devices
- **Environment variables** can still be used as fallback (see below)

## Settings Stored

The following settings are persisted:

1. **Dispatcharr Configuration**
   - URL, username, password

2. **Emby Configuration**
   - URL, username, password

3. **Database Configuration**
   - Database path

4. **Matching Preferences**
   - Apply options for station matching

## Docker Volume Mount

Your docker-compose.yml should have:
```yaml
volumes:
  - ./data:/data
```

This ensures settings.json and the database are persisted across container restarts.

## Environment Variable Fallback

You can still use environment variables if you prefer:

```yaml
environment:
  - DISPATCHARR_URL=http://dispatcharr:8000
  - DISPATCHARR_USERNAME=your_username
  - DISPATCHARR_PASSWORD=your_password
  - EMBY_URL=http://emby:8096
  - EMBY_USERNAME=your_username
  - EMBY_PASSWORD=your_password
  - DATABASE_PATH=/data/channelidentifiarr.db
```

**Note:** Settings saved via the web UI will override environment variables.

## Security

- Settings file is stored with **600 permissions** (owner read/write only)
- No encryption is applied (suitable for self-hosted environments)
- Keep your Docker volume secure with appropriate host permissions
- Don't commit `settings.json` to version control

## Migration

If you have existing settings in browser localStorage:
- They will be automatically migrated on first load
- localStorage settings will be cleared after successful migration
- This happens transparently when you visit the web UI

## File Location

Settings file: `/data/settings.json`

Example contents:
```json
{
  "dispatcharr": {
    "url": "http://dispatcharr:8000",
    "username": "admin",
    "password": "secret"
  },
  "emby": {
    "url": "http://emby:8096",
    "username": "admin",
    "password": "secret"
  },
  "database": {
    "path": "/data/channelidentifiarr.db"
  },
  "matching": {
    "applyStationId": true,
    "applyChannelName": false,
    "applyCallSign": false,
    "applyLogo": true
  }
}
```

## API Endpoints

- `GET /api/settings` - Load settings
- `POST /api/settings` - Save all settings
- `PATCH /api/settings` - Update specific settings
- `POST /api/settings/test-dispatcharr` - Test Dispatcharr connection
- `POST /api/settings/test-emby` - Test Emby connection
