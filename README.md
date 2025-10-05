# ChannelIdentifiarr

**Version: 0.1-alpha**

A web-based tool for identifying and managing TV channel lineups with Emby integration.

## Features

- 🔍 **Smart Channel Search** - Search channels by name, call sign, or station ID across multiple lineups
- 🌍 **Multi-Country Support** - Browse lineups from USA, Canada, UK, and more
- 📺 **Emby Integration** - Automatically add missing channels to Emby Live TV
- 🎯 **Intelligent Matching** - Parse and match channel names with country and resolution detection
- 🗺️ **Location-Based Preferences** - Prioritize lineups by country and ZIP code
- ⚡ **Real-time Progress** - Live updates when processing channels

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- A `channelidentifiarr.db` database file (see [Database Setup](#database-setup))

### Installation

1. Download the `docker-compose.yml` file:
```bash
wget https://raw.githubusercontent.com/egyptiangio/channelidentifiarr/main/docker-compose.yml
```

2. Edit `docker-compose.yml` and update the database path:
```yaml
volumes:
  - /path/to/channelidentifiarr.db:/data/channelidentifiarr.db:ro
```

3. Start the container:
```bash
docker-compose up -d
```

4. Open your browser to `http://localhost:9192`

## Database Setup

ChannelIdentifiarr requires a database of TV lineups and stations. You have two options:

### Option 1: Build Your Own Database

Use the included database creation script to build a custom database:

1. Create a CSV file with markets (country, postal code):
```csv
USA,90210
USA,10001
CAN,M5H
```

2. Run the database creation script:
```bash
python3 create_channelidentifiarr_db.py markets.csv
```

See the [Database Builder README](https://github.com/egyptiangio/channelidentifiarr-db) for detailed instructions.

### Option 2: Download Pre-built Database

Check the [Releases](https://github.com/egyptiangio/channelidentifiarr/releases) page for pre-built database files.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `/data/channelidentifiarr.db` | Path to the database file |
| `TZ` | `America/New_York` | Timezone for logging |

### Port

The application runs on port `9192` by default. Change it in `docker-compose.yml`:
```yaml
ports:
  - "8080:9192"  # Access on port 8080
```

## Emby Integration

### Setup

1. Navigate to the **Emby Settings** tab in ChannelIdentifiarr
2. Enter your Emby server details:
   - Server URL (e.g., `http://emby.local:8096`)
   - Username
   - Password
3. Click **Test Connection** to verify
4. Click **Save Settings**

### Features

- **Scan & Add Missing Listings** - Automatically identify Emby channels without lineup data and add them
- **Delete All Channel Logos** - Remove all custom logos from Emby Live TV channels
- **Clear All Channel Numbers** - Reset channel numbers for all Emby Live TV channels

All operations provide real-time progress updates.

## Usage

### Search for Channels

1. Navigate to the **Search** tab
2. Enter a channel name (e.g., "ESPN", "ABC", "CNN")
3. Optionally filter by:
   - Country
   - Lineup type (Cable, Satellite, OTA)
   - Resolution (SD, HD, UHD)
4. Click **Search**

### Browse Results

Results show:
- Channel name and call sign
- Logo (if available)
- Lineup information
- Channel number
- Country and resolution

### Emby Functions

#### Scan & Add Missing Listings

Identifies Emby channels missing lineup data and automatically adds them to the appropriate listing providers.

**Options:**
- **Country Preference** - Prioritize lineups from a specific country
- **ZIP Code Preference** - Prioritize lineups from a specific location

The algorithm ensures complete coverage using the minimum number of lineups.

#### Delete All Channel Logos

Removes all custom logos from Emby Live TV channels. Useful for resetting to default logos.

#### Clear All Channel Numbers

Resets all channel numbers to allow Emby to reassign them automatically.

## Docker Compose

Full example:

```yaml
services:
  channelidentifiarr:
    image: ghcr.io/egyptiangio/channelidentifiarr:latest
    container_name: channelidentifiarr
    restart: unless-stopped
    ports:
      - "9192:9192"
    volumes:
      - /path/to/channelidentifiarr.db:/data/channelidentifiarr.db:ro
    environment:
      - DATABASE_PATH=/data/channelidentifiarr.db
      - TZ=America/New_York
```

## Architecture

- **Backend**: Python Flask with SQLite database
- **Frontend**: Vanilla JavaScript with responsive UI
- **Server**: Gunicorn with gevent workers for SSE support
- **Container**: Python 3.11 slim base image

## Development

### Building Locally

```bash
docker build -t channelidentifiarr:local .
```

### Running Development Server

```bash
cd backend
pip install -r requirements.txt
python app.py
```

## Troubleshooting

### "Database not found"

Make sure the database path in `docker-compose.yml` points to a valid `channelidentifiarr.db` file.

### "No results found"

- Verify the database contains data for your search query
- Try broader search terms
- Check country/lineup filters

### Emby connection fails

- Verify server URL is accessible from the Docker container
- Check username/password are correct
- Ensure Emby server allows API access

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with data from the [Channels DVR](https://getchannels.com) API
- Designed for use with [Emby Media Server](https://emby.media)
- Channel data provided by Gracenote/TMS

## Support

- **Issues**: [GitHub Issues](https://github.com/egyptiangio/channelidentifiarr/issues)
- **Discussions**: [GitHub Discussions](https://github.com/egyptiangio/channelidentifiarr/discussions)

---

Made with ❤️ by [egyptiangio](https://github.com/egyptiangio)
