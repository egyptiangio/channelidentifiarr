# Channel Identifiarr Web - Complete Project Documentation

> **🚀 Quick Bootstrap for New Sessions**
>
> If starting a new session on this project:
> 1. **Current State**: Fully functional web app running in Docker on port 9192
> 2. **Recent Updates**: Settings consolidated to centralized Settings tab (no duplicate configs)
> 3. **Key Files**: `backend/app.py` (Flask API), `frontend/index.html` (Single-page app)
> 4. **To Deploy Changes**: `cd /mnt/nvme/scratch/channelidentifiarr-web && docker-compose build && docker-compose up -d`
> 5. **Database**: Read-only SQLite at `/mnt/nvme/scratch/channelidentifiarr/channelidentifiarr.db`
> 6. **Access**: http://localhost:9192 or http://your-server:9192

## Table of Contents
1. [Project Overview](#project-overview)
2. [Project History & Evolution](#project-history--evolution)
3. [Architecture Overview](#architecture-overview)
4. [Database Structure](#database-structure)
5. [API Endpoints](#api-endpoints)
6. [Channel Matching System](#channel-matching-system)
7. [Frontend Architecture](#frontend-architecture)
8. [Deployment](#deployment)
9. [Integrations](#integrations)
10. [File Structure](#file-structure)
11. [Development Guide](#development-guide)
12. [Current State & Recent Changes](#current-state--recent-changes)

---

## Project Overview

**Channel Identifiarr Web** is a modern web interface for searching and managing television channel/station data using the Gracenote database. It provides intelligent channel matching capabilities to help Dispatcharr users populate accurate EPG (Electronic Program Guide) data by matching their channels with Gracenote station IDs.

### Core Purpose
- Search 42,000+ TV stations from multiple countries
- Match Dispatcharr channels with Gracenote station IDs for EPG data
- Manage channel metadata (names, logos, call signs)
- Provide a web-based alternative to the original bash CLI tool

### Key Technologies
- **Backend**: Python Flask, SQLite, Gunicorn
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Deployment**: Docker, Docker Compose
- **Database**: SQLite with FTS5 (Full-Text Search)

---

## Project History & Evolution

### 1. Original Project: GlobalStationSearch (Bash CLI)
**Location**: `/mnt/inbox/globalstationsearch/`
**Version**: 2.6.0
**Type**: Bash CLI application

#### Key Features of Original:
- Complex bash script (`globalstationsearch.sh`) with 8000+ lines
- Modular architecture with libraries:
  - `/lib/core/` - Core search functionality
  - `/lib/integrations/` - Dispatcharr, Emby, Channels DVR integrations
  - `/lib/ui/` - Terminal UI components
  - `/lib/features/` - Additional features
- Channel name parsing with regex (`/lib/core/channel_parsing.sh`)
- Direct API integration with Channels DVR
- Interactive station ID matching
- Market-based database expansion

### 2. Database Creation: Channel Identifiarr
**Location**: `/mnt/nvme/scratch/channelidentifiarr/`
**Database**: `channelidentifiarr.db`
**Size**: ~500MB

#### Database Creation Process:
- Compiled from Gracenote API data
- Contains stations from multiple countries (USA, CAN, GBR, AUS, etc.)
- Includes station-lineup relationships
- Has logo URLs from TMS (Tribune Media Services)
- Fixed and optimized with indexes for performance

### 3. Web Interface: Channel Identifiarr Web (Current Project)
**Location**: `/mnt/nvme/scratch/channelidentifiarr-web/`
**Status**: Active Development
**URL**: http://server:9192

#### Evolution Timeline:
1. Started as simple search interface
2. Added Dispatcharr integration
3. Ported channel parsing logic from bash to Python
4. Added interactive matching system
5. Implemented settings management
6. Created bulk matching capabilities
7. Consolidated settings to centralized Settings tab (removed duplicate configs)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                             │
│                    http://server:9192                       │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST
┌──────────────────────▼──────────────────────────────────────┐
│                    Docker Container                         │
│              channelidentifiarr-web:9192                    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │               Gunicorn WSGI Server                 │    │
│  │                  (2 workers)                       │    │
│  └──────────────────────┬─────────────────────────────┘    │
│                         │                                   │
│  ┌──────────────────────▼─────────────────────────────┐    │
│  │              Flask Application                     │    │
│  │                 (app.py)                          │    │
│  │                                                   │    │
│  │  • Channel Search API                            │    │
│  │  • Matching Engine                               │    │
│  │  • Dispatcharr Integration                       │    │
│  │  • Database Queries                              │    │
│  └──────────────────────┬─────────────────────────────┘    │
│                         │                                   │
│  ┌──────────────────────▼─────────────────────────────┐    │
│  │            SQLite Database                         │    │
│  │      /data/channelidentifiarr.db                  │    │
│  │         (Read-Only Mount)                         │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                       │
                       │ External API Calls
┌──────────────────────▼──────────────────────────────────────┐
│                 Dispatcharr Server                          │
│                 http://server:9191                          │
└──────────────────────────────────────────────────────────────┘
```

---

## Database Structure

### Database Location
Primary: `/mnt/nvme/scratch/channelidentifiarr/channelidentifiarr.db`
Container Mount: `/data/channelidentifiarr.db` (read-only)

### Tables

#### 1. `stations`
```sql
CREATE TABLE stations (
    station_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    call_sign TEXT,
    type TEXT,
    logo_uri TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Indexes:
CREATE INDEX idx_stations_name ON stations(name);
CREATE INDEX idx_stations_call_sign ON stations(call_sign);
```

#### 2. `lineups`
```sql
CREATE TABLE lineups (
    lineup_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT,  -- OTA, CABLE, SATELLITE, VMVPD
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_lineups_type ON lineups(type);
```

#### 3. `station_lineups`
```sql
CREATE TABLE station_lineups (
    station_id TEXT,
    lineup_id TEXT,
    channel_number TEXT,
    channel_minor TEXT,
    video_type TEXT,  -- SDTV, HDTV, UHDTV
    tru_resolution TEXT,
    PRIMARY KEY (station_id, lineup_id),
    FOREIGN KEY (station_id) REFERENCES stations(station_id),
    FOREIGN KEY (lineup_id) REFERENCES lineups(lineup_id)
);
CREATE INDEX idx_station_lineups_station ON station_lineups(station_id);
CREATE INDEX idx_station_lineups_lineup ON station_lineups(lineup_id);
```

#### 4. `lineup_markets`
```sql
CREATE TABLE lineup_markets (
    lineup_id TEXT,
    market_id TEXT,
    country TEXT,  -- USA, CAN, GBR, etc.
    postal_code TEXT,
    PRIMARY KEY (lineup_id, market_id),
    FOREIGN KEY (lineup_id) REFERENCES lineups(lineup_id)
);
CREATE INDEX idx_lineup_markets_country ON lineup_markets(country);
```

#### 5. `stations_fts` (Full-Text Search)
```sql
CREATE VIRTUAL TABLE stations_fts USING fts5(
    station_id,
    name,
    call_sign,
    content=stations,
    content_rowid=rowid
);
```

### Database Statistics
- **Total Stations**: ~42,000+
- **Total Lineups**: ~30,000+
- **Station-Lineup Relationships**: ~11 million
- **Countries**: USA, CAN, GBR, AUS, MEX, and more
- **Logo Coverage**: ~85% of stations

---

## API Endpoints

### Base URL
Development: `http://localhost:9192`
Production: `http://server:9192`

### 1. General Endpoints

#### GET `/`
- **Purpose**: Serve frontend application
- **Response**: HTML page

#### GET `/api/health`
- **Purpose**: Health check endpoint
- **Response**:
```json
{
    "status": "healthy",
    "database": "connected",
    "stations_count": 42000
}
```

### 2. Search Endpoints

#### GET `/api/search/stations`
- **Purpose**: Search stations in database
- **Parameters**:
  - `q` (required): Search query
  - `country`: Filter by country code (USA, CAN, GBR)
  - `type`: Filter by lineup type (OTA, CABLE, SATELLITE, VMVPD)
  - `quality`: Filter by video quality (SDTV, HDTV, UHDTV)
  - `limit`: Max results (default: 50, -1 for unlimited)
- **Response**:
```json
{
    "query": "CNN",
    "count": 5,
    "results": [
        {
            "station_id": "10098",
            "name": "CNN",
            "call_sign": "CNN",
            "type": "Satellite",
            "logo_uri": "https://...",
            "has_logo": true
        }
    ]
}
```

#### GET `/api/station/{station_id}`
- **Purpose**: Get detailed station information
- **Response**:
```json
{
    "station": {
        "station_id": "10098",
        "name": "CNN",
        "call_sign": "CNN",
        "type": "Satellite",
        "logo_uri": "https://..."
    },
    "lineups": [
        {
            "lineup_id": "USA-CA-12345",
            "name": "Los Angeles - Cable",
            "type": "CABLE",
            "channel_number": "202"
        }
    ],
    "markets": ["USA", "CAN"]
}
```

### 3. Statistics Endpoints

#### GET `/api/stats`
- **Purpose**: Get database statistics
- **Response**:
```json
{
    "total_stations": 42000,
    "total_lineups": 30000,
    "total_relationships": 11000000,
    "stations_with_logos": 35000,
    "logo_percentage": 85,
    "countries": ["USA", "CAN", "GBR"],
    "lineup_types": {
        "OTA": 5000,
        "CABLE": 15000,
        "SATELLITE": 8000,
        "VMVPD": 2000
    }
}
```

#### GET `/api/metadata`
- **Purpose**: Get search metadata (countries, lineup types)
- **Response**:
```json
{
    "countries": [
        {"code": "USA", "name": "United States", "count": 25000},
        {"code": "CAN", "name": "Canada", "count": 5000}
    ],
    "lineup_types": ["OTA", "CABLE", "SATELLITE", "VMVPD"],
    "video_qualities": ["SDTV", "HDTV", "UHDTV"]
}
```

### 4. Dispatcharr Integration Endpoints

#### POST `/api/dispatcharr/test`
- **Purpose**: Test Dispatcharr connection
- **Body**:
```json
{
    "url": "http://192.168.1.100:9191",
    "username": "admin",
    "password": "password"
}
```

#### POST `/api/dispatcharr/channels`
- **Purpose**: Get channels from Dispatcharr
- **Body**: Same as test endpoint
- **Response**:
```json
{
    "channels": [
        {
            "id": 123,
            "name": "CNN HD",
            "gracenote_id": null,
            "tvg_id": "",
            "logo": ""
        }
    ],
    "total": 100
}
```

#### PATCH `/api/dispatcharr/channels/{channel_id}`
- **Purpose**: Update a Dispatcharr channel
- **Body**:
```json
{
    "url": "http://192.168.1.100:9191",
    "username": "admin",
    "password": "password",
    "update_data": {
        "gracenote_id": "10098",
        "name": "CNN",
        "call_sign": "CNN"
    }
}
```

### 5. Channel Matching Endpoints

#### POST `/api/match/suggest`
- **Purpose**: Get suggested matches for a channel
- **Body**:
```json
{
    "channel_name": "CNN USA HD",
    "channel_id": 123
}
```
- **Response**:
```json
{
    "channel_id": 123,
    "channel_name": "CNN USA HD",
    "parsed": {
        "clean_name": "CNN",
        "country": "USA",
        "resolution": "HDTV",
        "original": "CNN USA HD"
    },
    "matches": [
        {
            "station": {
                "station_id": "10098",
                "name": "CNN",
                "call_sign": "CNN",
                "logo_uri": "https://..."
            },
            "score": 0.95,
            "confidence": "high"
        }
    ],
    "total_found": 5
}
```

#### POST `/api/match/apply`
- **Purpose**: Apply a match to a Dispatcharr channel
- **Body**:
```json
{
    "channel_id": 123,
    "station_id": "10098",
    "dispatcharr_config": {
        "url": "http://192.168.1.100:9191",
        "username": "admin",
        "password": "password"
    }
}
```

#### POST `/api/match/batch`
- **Purpose**: Batch match multiple channels
- **Body**:
```json
{
    "channels": [
        {"id": 123, "name": "CNN HD"},
        {"id": 124, "name": "Fox News"}
    ]
}
```
- **Response**:
```json
{
    "total": 2,
    "matched": 1,
    "review_needed": 1,
    "no_match": 0,
    "errors": 0,
    "results": [...]
}
```

---

## Channel Matching System

### Channel Name Parsing Algorithm

The system uses a sophisticated regex-based parser ported from bash to Python:

#### 1. Special Character Handling
Separators replaced with spaces: `| ★ ◉ : ► ▶ → » ≫ — – = 〉 〈 ⟩ ⟨ ◆ ♦ ◊ ⬥ ● •`

#### 2. Country Detection
Detects and removes country indicators:
- **USA**: US, USA, UNITED STATES
- **GBR**: UK, GBR, BRITAIN, ENGLAND
- **CAN**: CA, CAN, CANADA
- **AUS**: AU, AUS, AUSTRALIA
- Plus 20+ other countries

#### 3. Resolution Detection
Identifies and removes resolution markers:
- **UHDTV**: 4K, UHD, UHDTV, Ultra HD
- **HDTV**: HD, FHD, 1080p, 1080i, 720p, 720i
- **SDTV**: SD, 480p, 480i

#### 4. Cleanup Operations
- Remove prefixes: CHANNEL, CH, NETWORK, TV, DIGITAL, CABLE, SATELLITE, STREAM, LIVE
- Remove suffixes: CHANNEL, NETWORK, TV, PLUS, +, 24/7
- Remove generic terms: THE, A, AN, AND, OR, OF, OFFICIAL, PREMIUM, EXCLUSIVE
- Remove special characters: `()[]{}#@$%^&*`
- Normalize spacing

#### 5. Matching Score Calculation
```python
def calculate_match_score(channel_name, station_data, parsed_channel):
    # Base score from string similarity (Levenshtein distance)
    name_score = SequenceMatcher(clean_channel, station_name).ratio()
    call_sign_score = SequenceMatcher(clean_channel, call_sign).ratio()

    # Take best score
    base_score = max(name_score, call_sign_score)

    # Bonuses
    if country_matches: score += 0.1
    if has_logo: score += 0.05

    return min(score, 1.0)
```

### Matching Workflow

1. **Automatic Matching**
   - Parse channel name
   - Search database with clean name
   - Calculate scores for results
   - Present top 5 matches

2. **Confidence Levels**
   - **High** (>80%): Auto-accept if setting enabled
   - **Medium** (50-80%): Requires user review
   - **Low** (<50%): Likely needs manual search

3. **Manual Override**
   - User can search any term
   - Select from results
   - Skip unmatchable channels

4. **Bulk Matching**
   - Process all channels at once
   - Auto-match high confidence
   - Queue others for review

---

## Frontend Architecture

### Technology Stack
- Pure JavaScript (ES6+)
- No frameworks (vanilla JS)
- LocalStorage for settings persistence
- Fetch API for backend communication

### Key Components

#### 1. Tab System
- **Search**: Station search interface
- **Dispatcharr Integration**: Channel management (reads settings from Settings tab)
- **Channel Matching**: Interactive matching interface
- **Settings**: Centralized configuration management (all app settings in one place)

#### 2. State Management
```javascript
// Global state variables
let currentResults = [];        // Search results
let sortColumn = null;          // Table sorting
let sortDirection = 'asc';      // Sort direction
let dispatcharrChannels = [];   // Loaded channels
let matchingQueue = [];         // Channels to match
let currentMatchIndex = 0;      // Current position
let matchingResults = [];       // Match results
let isMatching = false;         // Matching state
```

#### 3. Settings System

**Important Update (October 2025)**: Settings have been consolidated to a single location. All configuration is now managed through the Settings tab only.

```javascript
// Centralized LocalStorage structure - key: 'channelIdentifiarrSettings'
{
    "dispatcharr": {
        "url": "http://192.168.1.100:9191",
        "port": "9191",
        "username": "admin",
        "password": "password"
    },
    "matching": {
        "autoAcceptHigh": true,
        "updateNames": true,
        "updateLogos": true
    },
    "emby": {
        // Future: Emby configuration
    }
}
```

**Key Changes:**
- Removed duplicate Dispatcharr settings from Dispatcharr tab
- All settings now use single `channelIdentifiarrSettings` localStorage key
- Added connection banner that guides users to Settings tab when not configured
- Removed `toggleDispatcharrSettings()` function
- Old localStorage keys (`dispatcharr_url`, `dispatcharr_username`, `dispatcharr_password`) deprecated

#### 4. UI Features
- Dark theme with gradient backgrounds
- Responsive design
- Real-time progress tracking
- Color-coded confidence indicators
- Export to CSV functionality
- Sortable tables
- Collapsible sections

---

## Deployment

### Docker Configuration

#### Dockerfile (`backend/Dockerfile`)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y sqlite3 curl
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN mkdir -p /data
EXPOSE 5000
HEALTHCHECK CMD curl -f http://localhost:5000/api/health || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
```

#### Docker Compose (`docker-compose.yml`)
```yaml
version: '3.8'
services:
  channelidentifiarr-web:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: channelidentifiarr-web
    restart: unless-stopped
    ports:
      - "9192:5000"
    volumes:
      - /mnt/nvme/scratch/channelidentifiarr/channelidentifiarr.db:/data/channelidentifiarr.db:ro
      - ./frontend:/app/frontend:ro
    environment:
      - DATABASE_PATH=/data/channelidentifiarr.db
      - TZ=America/New_York
    networks:
      - channelidentifiarr-net
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

networks:
  channelidentifiarr-net:
    driver: bridge
```

### Deployment Commands

#### Initial Deployment
```bash
cd /mnt/nvme/scratch/channelidentifiarr-web
docker-compose build
docker-compose up -d
```

#### Update Deployment
```bash
cd /mnt/nvme/scratch/channelidentifiarr-web
# Make code changes
docker-compose build
docker-compose up -d
```

#### View Logs
```bash
docker-compose logs -f
```

#### Restart Service
```bash
docker-compose restart
```

#### Stop Service
```bash
docker-compose down
```

### Port Configuration
- **Internal Port**: 5000 (Flask/Gunicorn)
- **External Port**: 9192 (Docker mapped)
- **Access URL**: http://server:9192

---

## Integrations

### 1. Dispatcharr Integration

**Purpose**: Channel management and EPG data population

**Connection Requirements**:
- Dispatcharr URL (e.g., http://192.168.1.100:9191)
- Username and password for authentication
- Network connectivity between containers/services

**API Endpoints Used**:
- `GET /api/channels/` - List all channels
- `PATCH /api/channels/{id}/` - Update channel fields
- `GET /api/auth/` - Authentication test

**Fields Mapped**:
- `tvc_guide_stationid` ← station_id (Gracenote ID)
- `name` ← station name
- `tvg_id` ← call_sign
- `logo` ← logo_uri

### 2. Future: Emby Integration

**Status**: Planned but not implemented

**Planned Features**:
- Direct connection to Emby server
- Sync channel data
- Update channel metadata
- Populate missing listingIds

### 3. Future: Channels DVR Integration

**Status**: Available in original bash tool, not ported

**Original Features**:
- Direct API search
- Channel addition
- Lineup management

---

## File Structure

```
/mnt/nvme/scratch/channelidentifiarr-web/
├── backend/
│   ├── app.py                 # Flask application (1000+ lines)
│   ├── Dockerfile              # Container configuration
│   └── requirements.txt        # Python dependencies
├── frontend/
│   └── index.html             # Complete web UI (1850+ lines)
├── data/                      # Data directory (empty, DB mounted here)
├── docker-compose.yml         # Container orchestration
├── fix_database.py           # Database repair script
├── README.md                 # User documentation
└── PROJECT_DOCUMENTATION.md  # This file

/mnt/nvme/scratch/channelidentifiarr/
├── channelidentifiarr.db     # Main SQLite database (~500MB)
└── dispatcharr_plugin/        # Related plugin code

/mnt/inbox/globalstationsearch/
├── globalstationsearch.sh     # Original bash script (8000+ lines)
├── lib/
│   ├── core/
│   │   ├── channel_parsing.sh # Channel name parser
│   │   ├── search.sh         # Search functions
│   │   └── ...
│   ├── integrations/
│   │   ├── dispatcharr.sh    # Dispatcharr integration
│   │   ├── emby.sh          # Emby integration
│   │   └── cdvr.sh          # Channels DVR integration
│   └── ui/                   # Terminal UI components
├── cache/                    # Cached API responses
└── data/                     # Data files
```

---

## Development Guide

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development)
- SQLite3 tools
- Git

### Local Development Setup

#### Backend Development
```bash
cd /mnt/nvme/scratch/channelidentifiarr-web/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
DATABASE_PATH=/mnt/nvme/scratch/channelidentifiarr/channelidentifiarr.db \
python app.py
```

#### Frontend Development
```bash
# Frontend is single HTML file
# Edit: /mnt/nvme/scratch/channelidentifiarr-web/frontend/index.html
# Refresh browser to see changes
```

### Adding New Features

#### 1. New API Endpoint
```python
# In app.py
@app.route('/api/new-endpoint', methods=['GET', 'POST'])
def new_endpoint():
    try:
        # Implementation
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
```

#### 2. New Frontend Feature
```javascript
// In index.html
function newFeature() {
    fetch('/api/new-endpoint', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({data: 'value'})
    })
    .then(r => r.json())
    .then(data => {
        // Handle response
    });
}
```

### Testing

#### API Testing
```bash
# Health check
curl http://localhost:9192/api/health

# Search test
curl "http://localhost:9192/api/search/stations?q=CNN&limit=5"

# Match test
curl -X POST http://localhost:9192/api/match/suggest \
  -H "Content-Type: application/json" \
  -d '{"channel_name": "CNN USA HD"}'
```

#### Database Testing
```bash
# Connect to database
sqlite3 /mnt/nvme/scratch/channelidentifiarr/channelidentifiarr.db

# Sample queries
.tables
SELECT COUNT(*) FROM stations;
SELECT * FROM stations WHERE name LIKE '%CNN%' LIMIT 5;
.quit
```

### Common Issues & Solutions

#### Issue: Changes not reflecting
**Solution**: Rebuild Docker container
```bash
docker-compose build && docker-compose up -d
```

#### Issue: Database locked
**Solution**: Database is read-only, ensure no writes attempted

#### Issue: Port already in use
**Solution**: Change port in docker-compose.yml

#### Issue: Slow searches
**Solution**: Check indexes exist:
```sql
.indexes stations
```

### Performance Optimization

#### Database Indexes (Already Applied)
- Station name and call_sign indexes
- Lineup type indexes
- Country indexes
- FTS5 full-text search

#### Query Optimization
- Use LIMIT for large result sets
- Leverage FTS5 for text searches
- Use prepared statements (parameterized queries)

#### Frontend Optimization
- Debounce search input
- Lazy load large lists
- Use pagination for results

---

## Security Considerations

### Current Implementation
- Read-only database mount
- No user authentication (planned)
- Credentials stored in localStorage (client-side)
- CORS enabled for all origins

### Recommended Improvements
1. Implement user authentication
2. Use environment variables for sensitive data
3. Add rate limiting
4. Implement HTTPS with reverse proxy
5. Restrict CORS origins
6. Add input validation and sanitization
7. Implement API key authentication

---

## Future Enhancements

### High Priority
1. **User Authentication System**
   - Login/logout functionality
   - Session management
   - Role-based access control

2. **Complete Emby Integration**
   - Direct server connection
   - Channel synchronization
   - Metadata updates

3. **Advanced Matching Features**
   - Machine learning-based matching
   - Fuzzy matching improvements
   - Batch undo/redo

### Medium Priority
1. **Database Management**
   - Automatic updates from Gracenote
   - Custom station addition
   - Database backup/restore UI

2. **UI/UX Improvements**
   - Modern framework (React/Vue)
   - Better mobile responsiveness
   - Dark/light theme toggle

3. **Analytics Dashboard**
   - Matching statistics
   - Usage metrics
   - Performance monitoring

### Low Priority
1. **Additional Integrations**
   - Plex integration
   - Jellyfin support
   - TVHeadend compatibility

2. **Advanced Features**
   - Channel grouping
   - Custom EPG sources
   - Scheduled tasks

---

## Maintenance Notes

### Regular Tasks
1. **Database Updates**: Check for Gracenote updates monthly
2. **Docker Updates**: Update base images quarterly
3. **Dependency Updates**: Update Python packages monthly
4. **Backup**: Backup database and settings weekly

### Monitoring
- Check Docker logs for errors
- Monitor disk space (database can grow)
- Track API response times
- Monitor memory usage

### Backup Strategy
```bash
# Backup database
cp /mnt/nvme/scratch/channelidentifiarr/channelidentifiarr.db \
   /backup/channelidentifiarr_$(date +%Y%m%d).db

# Backup configuration
cd /mnt/nvme/scratch/channelidentifiarr-web
tar -czf /backup/channelidentifiarr-web_$(date +%Y%m%d).tar.gz .
```

---

## Current State & Recent Changes

### Latest Session Updates (October 2025)

#### Settings Consolidation ✅
**Problem**: Dispatcharr settings were duplicated in two places (Dispatcharr tab and Settings tab), causing confusion and potential sync issues.

**Solution Implemented**:
1. Removed all Dispatcharr configuration UI from the Dispatcharr tab
2. Consolidated to single Settings tab with centralized localStorage key: `channelIdentifiarrSettings`
3. Added connection status banner on Dispatcharr tab that guides users to Settings when not configured
4. Updated all JavaScript functions to use consolidated settings:
   - `checkDispatcharrSettings()` - Validates settings and shows/hides banner
   - `loadDispatcharrChannels()` - Uses centralized settings
   - Removed: `toggleDispatcharrSettings()`, `loadDispatcharrSettings()`, `saveDispatcharrSettings()`
5. Deprecated old localStorage keys: `dispatcharr_url`, `dispatcharr_username`, `dispatcharr_password`

**Files Modified**:
- `frontend/index.html` (lines 713-820, 863-867)

#### Current Feature Status

**✅ Fully Implemented & Working**:
- Station search with 42,000+ records
- Dispatcharr channel loading and display
- Channel name parsing (ported from bash)
- Interactive channel matching interface
- Bulk channel matching
- Settings management (consolidated)
- CSV export functionality
- Docker deployment

**🚧 Partially Implemented**:
- Manual search during matching (implemented but needs testing)
- Bulk match review workflow (implemented but needs testing)

**📋 Planned/TODO**:
- Emby integration (settings structure ready)
- Settings validation before save
- Match history/audit log
- Undo match functionality
- Export match results

### Application Structure Overview

```
Web Interface (Port 9192)
├── Search Tab - Query 42K+ stations
├── Dispatcharr Tab - View channels (requires Settings config)
├── Channel Matching Tab - Interactive matching workflow
└── Settings Tab - Centralized configuration (ALL settings here)
```

### Key JavaScript Functions (frontend/index.html)

**Tab Management**:
- `switchTab(tabName)` - Handles tab switching, shows/hides content

**Settings System**:
- `loadSettings()` - Loads from localStorage on page load
- `saveSettings()` - Saves to localStorage.channelIdentifiarrSettings
- `testDispatcharrSettings()` - Tests Dispatcharr connection

**Dispatcharr Integration**:
- `checkDispatcharrSettings()` - Validates config, shows banner if missing
- `loadDispatcharrChannels()` - Fetches channels from Dispatcharr API
- `displayDispatcharrChannels(channels)` - Renders channel table

**Channel Matching**:
- `startChannelMatching()` - Begins interactive matching workflow
- `matchNextChannel()` - Processes next channel in queue
- `displaySuggestedMatches(matches)` - Shows AI-suggested matches
- `acceptMatch(stationId, channel)` - Applies match to Dispatcharr
- `skipCurrentChannel()` - Skips channel
- `performManualSearch()` - Manual station search override

**Bulk Operations**:
- `startBulkMatching()` - Automated batch matching
- `reviewBulkMatches(results)` - Review low-confidence matches

### Python Backend (backend/app.py)

**Key API Endpoints**:
- `/api/search/stations` - Search Gracenote database
- `/api/dispatcharr/channels` - Load channels from Dispatcharr
- `/api/dispatcharr/test` - Test Dispatcharr connection
- `/api/match/suggest` - Get AI-suggested matches for channel
- `/api/match/apply` - Apply match to Dispatcharr
- `/api/match/batch` - Bulk match all channels

**Core Functions**:
- `parse_channel_name(name)` - Extracts clean name, country, resolution
- `calculate_match_score(channel, station, parsed)` - Fuzzy matching algorithm
- `suggest_matches()` - Returns top 5 matches with confidence scores

### Current Deployment

**Docker Container**: `channelidentifiarr-web`
- **Status**: Running and healthy
- **Port**: 9192 (host) → 5000 (container)
- **Image**: Built from local Dockerfile
- **WSGI Server**: Gunicorn with 2 workers
- **Volumes**:
  - Database: `/mnt/nvme/scratch/channelidentifiarr/channelidentifiarr.db:/data/channelidentifiarr.db:ro`
  - Backend: `./backend:/app`
  - Frontend: `./frontend:/app/frontend`

**To Restart/Rebuild**:
```bash
cd /mnt/nvme/scratch/channelidentifiarr-web
docker-compose build  # Rebuild if code changed
docker-compose restart  # Quick restart
docker-compose down && docker-compose up -d  # Full restart
```

### Testing Changes

After making code changes:
1. Rebuild container: `docker-compose build`
2. Restart: `docker-compose up -d`
3. Check logs: `docker-compose logs -f`
4. Test API: `curl http://localhost:9192/api/stats`
5. Test frontend: Open http://localhost:9192 in browser

### Troubleshooting Recent Issues

**Issue**: Tabs not displaying content
- **Cause**: `switchTab()` wasn't handling new tab names
- **Fix**: Added cases for 'matching' and 'settings', explicit display styling

**Issue**: Settings not persisting
- **Cause**: Using wrong localStorage key
- **Fix**: Consolidated to `channelIdentifiarrSettings` key

**Issue**: Dispatcharr tab showing "not configured"
- **Cause**: Reading from old localStorage keys
- **Fix**: Updated to use centralized settings structure

---

## Contact & Support

### Resources
- Original GlobalStationSearch: Part of Dispatcharr ecosystem
- Database Source: Gracenote/TMS APIs
- Related Projects: Dispatcharr, Channels DVR

### Known Issues
1. Some international stations missing logos
2. FTS5 search can miss partial matches
3. Bulk matching can timeout with 500+ channels
4. Settings not validated before save

### Debug Mode
Enable debug logging in app.py:
```python
logging.basicConfig(level=logging.DEBUG)
```

View debug logs:
```bash
docker-compose logs -f | grep DEBUG
```

---

## License & Credits

This project builds upon:
- GlobalStationSearch by egyptiangio
- Gracenote database content
- Open source libraries: Flask, SQLite, Docker

---

*Last Updated: October 2024*
*Documentation Version: 1.0*