# Channel Identifiarr Web - Quick Start Guide

## 🚀 For New Claude Sessions

If you're Claude starting a new session on this project, here's everything you need to know:

### Current Status
✅ **Production Ready** - Fully functional web application running in Docker

### Essential Info
- **Location**: `/mnt/nvme/scratch/channelidentifiarr-web/` or `/srv/dev-disk-by-uuid-c332869f-d034-472c-a641-ccf1f28e52d6/scratch/channelidentifiarr-web/`
- **Access URL**: http://localhost:9192
- **Docker Container**: `channelidentifiarr-web`
- **Port**: 9192 (host) → 5000 (container)
- **Database**: `/mnt/nvme/scratch/channelidentifiarr/channelidentifiarr.db` (read-only)

### Project Structure
```
channelidentifiarr-web/
├── backend/
│   └── app.py                 # Flask API (500+ lines)
├── frontend/
│   └── index.html            # Single-page app (1850+ lines)
├── docker-compose.yml        # Docker config
├── Dockerfile               # Container build
├── requirements.txt         # Python dependencies
├── PROJECT_DOCUMENTATION.md # Complete docs (1167 lines)
└── QUICKSTART.md           # This file
```

### Architecture
```
Browser (Port 9192)
    ↓
Docker Container
    ↓
Gunicorn (2 workers)
    ↓
Flask App (app.py)
    ↓
SQLite Database (42K+ stations)
    ↓
Dispatcharr API (external)
```

### Main Features
1. **Search Tab** - Search 42,000+ TV stations from Gracenote database
2. **Dispatcharr Tab** - View channels from Dispatcharr (requires Settings config)
3. **Channel Matching Tab** - Interactive channel matching with AI suggestions
4. **Settings Tab** - Centralized configuration (ALL settings stored here)

### Key Technologies
- **Backend**: Python 3.12, Flask, SQLite, Gunicorn
- **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3
- **Deployment**: Docker, docker-compose
- **Database**: SQLite with FTS5 full-text search

---

## ⚡ Common Tasks

### Deploy Code Changes
```bash
cd /mnt/nvme/scratch/channelidentifiarr-web
docker-compose build
docker-compose up -d
```

### Quick Restart (no code changes)
```bash
cd /mnt/nvme/scratch/channelidentifiarr-web
docker-compose restart
```

### View Logs
```bash
docker-compose logs -f
```

### Check Status
```bash
docker-compose ps
curl http://localhost:9192/api/stats
```

### Test API Endpoint
```bash
# Test search
curl -s "http://localhost:9192/api/search/stations?q=CNN&limit=5" | python3 -m json.tool

# Test stats
curl -s http://localhost:9192/api/stats | python3 -m json.tool
```

---

## 📋 Recent Changes (October 2025)

### Settings Consolidation ✅
**What Changed**: All Dispatcharr settings moved to centralized Settings tab

**Why**: Duplicate settings in two places caused confusion and sync issues

**Impact**:
- Old localStorage keys deprecated: `dispatcharr_url`, `dispatcharr_username`, `dispatcharr_password`
- New centralized key: `channelIdentifiarrSettings`
- Dispatcharr tab now shows banner when settings missing
- All functions updated to use centralized config

**Files Modified**:
- `frontend/index.html` (removed duplicate UI, updated functions)

---

## 🔧 API Endpoints

### Core Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve frontend HTML |
| `/api/stats` | GET | Database statistics |
| `/api/search/stations` | GET | Search stations (`?q=CNN&limit=10`) |
| `/api/dispatcharr/channels` | POST | Load channels from Dispatcharr |
| `/api/dispatcharr/test` | POST | Test Dispatcharr connection |
| `/api/match/suggest` | POST | Get AI match suggestions |
| `/api/match/apply` | POST | Apply match to Dispatcharr |
| `/api/match/batch` | POST | Bulk match all channels |

### Example Request
```bash
curl -X POST http://localhost:9192/api/match/suggest \
  -H "Content-Type: application/json" \
  -d '{"channel_name": "CNN USA HD"}'
```

---

## 🧠 Key Concepts

### Channel Name Parsing
The system uses regex patterns (ported from bash) to parse channel names:
- **Clean Name**: Removes prefixes, suffixes, special chars
- **Country Detection**: USA, CAN, GBR, etc.
- **Resolution Detection**: 4K, HD, SD

Example:
```
Input:  "USA ★ CNN HD (East)"
Output: {
  "clean_name": "CNN",
  "country": "USA",
  "resolution": "HD"
}
```

### Match Scoring
Confidence scores (0.0 to 1.0) based on:
- Fuzzy string matching (name similarity)
- Country match bonus (+0.1)
- Logo availability bonus (+0.05)

Thresholds:
- **High Confidence**: >0.8 (green, auto-accept)
- **Medium Confidence**: 0.5-0.8 (yellow, review)
- **Low Confidence**: <0.5 (red, needs manual search)

### Settings Storage
All settings stored in localStorage under `channelIdentifiarrSettings`:
```javascript
{
  "dispatcharr": {
    "url": "http://192.168.1.100:9191",
    "username": "admin",
    "password": "password"
  },
  "matching": {
    "autoAcceptHigh": true,
    "updateNames": true,
    "updateLogos": true
  }
}
```

---

## 🐛 Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Database not found
Verify database mount:
```bash
ls -lh /mnt/nvme/scratch/channelidentifiarr/channelidentifiarr.db
docker exec channelidentifiarr-web ls -lh /data/channelidentifiarr.db
```

### Settings not saving
- Clear browser localStorage
- Check browser console for errors
- Verify JSON structure in localStorage

### Tabs not showing content
- Hard refresh browser (Ctrl+F5 / Cmd+Shift+R)
- Check `switchTab()` function handles tab name
- Verify `display: block` style is applied

---

## 📚 Related Projects

### 1. Global Station Search (Bash CLI)
**Location**: `/mnt/nvme/scratch/globalstationsearch/`
- Original bash implementation
- Source of channel parsing logic
- Direct SQLite queries

### 2. Channel Identifiarr (Legacy)
**Location**: `/mnt/nvme/scratch/channelidentifiarr/`
- Contains the Gracenote database
- Database path: `channelidentifiarr.db`
- 42,000+ station records

### 3. Dispatcharr
**External Service** - Channel/EPG management system
- API endpoint configured in Settings
- Requires username/password auth
- Provides channel list and accepts Gracenote station IDs

---

## 🎯 Development Workflow

### Making Changes
1. Edit code in `backend/app.py` or `frontend/index.html`
2. Rebuild container: `docker-compose build`
3. Restart: `docker-compose up -d`
4. Test in browser: http://localhost:9192
5. Check logs: `docker-compose logs -f`

### Testing APIs
```bash
# Test stats endpoint
curl http://localhost:9192/api/stats

# Test search
curl "http://localhost:9192/api/search/stations?q=CNN&limit=5"

# Test match suggestion
curl -X POST http://localhost:9192/api/match/suggest \
  -H "Content-Type: application/json" \
  -d '{"channel_name": "CNN HD"}'
```

### Debugging Frontend
- Open browser DevTools (F12)
- Check Console tab for JavaScript errors
- Check Network tab for API calls
- Inspect localStorage: `localStorage.getItem('channelIdentifiarrSettings')`

### Debugging Backend
```bash
# View live logs
docker-compose logs -f

# Execute commands in container
docker exec -it channelidentifiarr-web bash

# Test database access
docker exec channelidentifiarr-web sqlite3 /data/channelidentifiarr.db "SELECT COUNT(*) FROM stations;"
```

---

## 🔮 Future Enhancements

### Planned Features
- [ ] Emby integration (settings structure ready)
- [ ] Settings validation before save
- [ ] Match history/audit log
- [ ] Undo match functionality
- [ ] Export match results to CSV
- [ ] Channel import from CSV
- [ ] Advanced filtering (by country, resolution)
- [ ] Batch operations on search results

### Partially Implemented (Needs Testing)
- Manual search during matching
- Bulk match review workflow

---

## 📖 Full Documentation

For complete details, see:
- **PROJECT_DOCUMENTATION.md** - Comprehensive 1167-line reference
  - Complete API documentation
  - Database schema
  - Channel matching algorithm
  - Deployment details
  - File structure
  - Development guide

---

## ✅ Health Check

To verify everything is working:

```bash
# 1. Container is running
docker ps | grep channelidentifiarr

# 2. Database is accessible
docker exec channelidentifiarr-web sqlite3 /data/channelidentifiarr.db "SELECT COUNT(*) FROM stations;"
# Expected: 42000+

# 3. Web server responding
curl -I http://localhost:9192
# Expected: HTTP/1.1 200 OK

# 4. API functioning
curl http://localhost:9192/api/stats
# Expected: JSON with station counts

# 5. Search working
curl "http://localhost:9192/api/search/stations?q=CNN&limit=1"
# Expected: JSON with CNN results
```

---

## 💡 Tips for Claude

- **Always check current state first**: Run `docker-compose ps` and test API
- **Settings are centralized**: Don't create duplicate config UIs
- **Test after changes**: Rebuild container and verify in browser
- **Check logs for errors**: `docker-compose logs -f` is your friend
- **Frontend is vanilla JS**: No framework, all in one HTML file
- **Database is read-only**: Can't modify station data, only query
- **Port is 9192**: Not 5000, not 8588, not 8080 - always 9192

---

**Last Updated**: October 2025
**Status**: Production Ready ✅
**Docker Container**: channelidentifiarr-web (running)
**URL**: http://localhost:9192
