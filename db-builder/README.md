# ChannelIdentifiarr Database Creator

A Python script for creating a comprehensive SQLite database of TV lineups and stations using the Channels DVR public API.

## Overview

This tool builds a normalized database containing:
- **Markets**: Geographic locations (country + postal code)
- **Lineups**: TV service providers available in each market
- **Stations**: TV channels with logos and metadata
- **Relationships**: Which stations appear in which lineups, with channel numbers

The database is optimized for searching and matching TV channels across different providers and markets.

## Requirements

- Python 3.8 or higher
- Internet connection
- Python packages: `requests` (all other dependencies are in Python stdlib)

Install dependencies:
```bash
pip install requests
```

## Usage

### Prerequisites

**IMPORTANT: You must have a local Channels DVR server running.**

This script requires access to your Channels DVR server's API. You'll need to provide your server's IP address and port (default: 8089).

### Basic Usage

```bash
python3 create_channelidentifiarr_db.py markets.csv --server http://192.168.1.100:8089
```

This will:
1. Read markets from the CSV file
2. Fetch lineup and station data from your Channels DVR server
3. Create `channelidentifiarr.db` SQLite database
4. Build optimized indexes for fast queries
5. Create a checkpoint file for resumability

### Command-Line Options

```bash
# Use more workers for faster processing (default: 4, max: 10)
python3 create_channelidentifiarr_db.py markets.csv --server http://192.168.1.100:8089 --workers 6

# Force refresh all data (ignore existing database)
python3 create_channelidentifiarr_db.py markets.csv --server http://192.168.1.100:8089 --force

# Skip station enhancement phase (faster but less metadata)
python3 create_channelidentifiarr_db.py markets.csv --server http://192.168.1.100:8089 --skip-enhancement

# Run only enhancement on existing database
python3 create_channelidentifiarr_db.py markets.csv --server http://192.168.1.100:8089 --enhance-only

# Keep checkpoint file after completion
python3 create_channelidentifiarr_db.py markets.csv --server http://192.168.1.100:8089 --no-cleanup
```

## CSV File Format

The input CSV file must contain markets in the following format:

```csv
country,postal_code
USA,90210
USA,10001
USA,60601
CAN,M5H
GBR,SW1A
```

### Important Notes:

1. **No header row**: The CSV should contain only data rows (country, postal code)
2. **Country codes**: Use ISO 3166-1 alpha-3 codes:
   - `USA` - United States
   - `CAN` - Canada
   - `GBR` - United Kingdom
3. **Postal codes**:
   - **USA**: 5-digit ZIP codes (e.g., `90210`)
   - **Canada**: First 3 characters of postal code (e.g., `M5H`)
   - **UK**: Outward code only (e.g., `SW1A`)

### Example CSV Files

**USA markets (sample):**
```csv
USA,90210
USA,10001
USA,60601
USA,30301
USA,94102
```

**Canadian markets:**
```csv
CAN,M5H
CAN,V6B
CAN,H3A
```

**UK markets:**
```csv
GBR,SW1A
GBR,W1A
GBR,EC1A
```

**Mixed markets:**
```csv
USA,90210
CAN,M5H
GBR,SW1A
USA,10001
```

## How It Works

### Architecture

The script uses a **producer-consumer architecture** for optimal performance:

- **Multiple producer threads** (default: 4) fetch data from the API in parallel
- **Single consumer thread** writes to the database sequentially (eliminates lock contention)
- **Queue-based communication** ensures thread-safe operation

### Processing Phases

1. **Ingestion Phase**:
   - Fetches lineups for each market
   - Fetches stations (channels) for each lineup
   - Stores base station data (call sign, logo)
   - Uses 4 workers by default (optimal for most systems)

2. **Enhancement Phase**:
   - Fetches detailed metadata for each station
   - Adds station names, types, broadcast languages
   - Uses 10 workers for maximum throughput
   - Can be skipped with `--skip-enhancement`

3. **Indexing Phase**:
   - Creates optimized database indexes
   - Improves query performance
   - Happens automatically at the end

### Resumability

The script supports **graceful interruption and resumption**:

- Progress is checkpointed to `channelidentifiarr_registry.json`
- If interrupted (Ctrl+C), you can re-run the same command
- It will resume from where it left off
- Different CSV files are tracked separately by hash

### Performance

Typical performance (will vary by network speed):

- **Ingestion**: ~2-4 markets per second with 4 workers
- **Enhancement**: ~5-10 stations per second with 10 workers
- **Total time** for 1,000 USA markets: 10-20 minutes

Use `--workers 6` or `--workers 8` for faster processing on good connections.

## Database Schema

### Tables

**markets**
- `country` (TEXT): ISO 3166-1 alpha-3 country code
- `postal_code` (TEXT): Normalized postal code
- `city`, `state`, `timezone`: Geographic metadata

**lineups**
- `lineup_id` (TEXT): Unique lineup identifier
- `name` (TEXT): Provider name (e.g., "DirecTV")
- `location` (TEXT): Service area description
- `type` (TEXT): Lineup type (Cable, Satellite, OTA, etc.)
- `device` (TEXT): Device/platform type
- `mso_id`, `mso_name`: Cable operator information

**stations**
- `station_id` (TEXT): Unique station identifier
- `call_sign` (TEXT): FCC call sign (e.g., "KABC")
- `name` (TEXT): Station name (e.g., "ABC 7 Los Angeles")
- `type` (TEXT): Station type
- `bcast_langs` (TEXT): Broadcast languages (JSON array)
- `logo_uri`, `logo_width`, `logo_height`: Logo metadata
- `source` (TEXT): 'base' or 'enhanced'

**station_lineups**
- `station_id`, `lineup_id`: Foreign keys
- `channel_number` (TEXT): Channel number in this lineup
- `affiliate_id`, `affiliate_call_sign`: Network affiliation
- `signal_type`, `video_type`, `tru_resolution`: Technical specs

**lineup_markets**
- `lineup_id`, `country`, `postal_code`: Maps lineups to markets

### Example Queries

```sql
-- Find all stations in a market
SELECT DISTINCT s.*
FROM stations s
JOIN station_lineups sl ON s.station_id = sl.station_id
JOIN lineup_markets lm ON sl.lineup_id = lm.lineup_id
WHERE lm.country = 'USA' AND lm.postal_code = '90210';

-- Find all lineups offering a specific station
SELECT l.*
FROM lineups l
JOIN station_lineups sl ON l.lineup_id = sl.lineup_id
WHERE sl.station_id = '10021';

-- Search stations by name
SELECT * FROM stations
WHERE LOWER(name) LIKE '%espn%';

-- Count stations per lineup
SELECT l.name, COUNT(DISTINCT sl.station_id) as station_count
FROM lineups l
JOIN station_lineups sl ON l.lineup_id = sl.lineup_id
GROUP BY l.lineup_id
ORDER BY station_count DESC;
```

## Output Files

After successful completion:

- `channelidentifiarr.db` - SQLite database with all data and indexes
- `channelidentifiarr_registry.json` - Checkpoint file (auto-deleted unless `--no-cleanup`)
- `registry_snapshot_YYYYMMDD_HHMMSS.json` - Archived checkpoint (if completed successfully)

## Troubleshooting

### "CSV file not found"
Ensure the path to your CSV file is correct. Use relative or absolute paths.

### "No lineups found" errors
Some postal codes may not have TV lineups available. This is normal - the script will log these and continue.

### Script interrupted
Simply re-run the same command. The script will resume from the last checkpoint.

### Slow performance
- Increase workers: `--workers 6` or `--workers 8`
- Check your internet connection speed
- API rate limiting may occur with >10 workers

### Out of memory
Reduce workers: `--workers 2`

### Database locked errors
These should not occur with the single-consumer design. If they do:
1. Close any other programs accessing the database
2. Delete the `.db-wal` and `.db-shm` files
3. Re-run the script

## Advanced Usage

### Creating Regional Databases

For better performance, create separate databases per region:

```bash
# USA only
python3 create_channelidentifiarr_db.py usa_markets.csv

# Canada only
python3 create_channelidentifiarr_db.py canada_markets.csv

# Then merge if needed using SQLite ATTACH
```

### Testing with Small Sample

Create a test CSV with a few markets first:

```csv
USA,90210
USA,10001
```

```bash
python3 create_channelidentifiarr_db.py test_markets.csv
```

### Re-running Enhancement Only

If you skipped enhancement initially:

```bash
# Initial run without enhancement
python3 create_channelidentifiarr_db.py markets.csv --skip-enhancement

# Add enhancement later
python3 create_channelidentifiarr_db.py markets.csv --enhance-only
```

## API Information

This script uses your local Channels DVR server's API:
- **Base URL**: Provided via `--server` argument (e.g., `http://192.168.1.100:8089`)
- **No API key required**
- **Endpoints used**:
  - `/tms/lineups/{country}/{postal_code}` - Get lineups for a market
  - `/dvr/guide/stations/{lineup_id}` - Get stations in a lineup
  - `/tms/stations/{call_sign}` - Get detailed station metadata

**Note:** You must have an active Channels DVR server subscription to use this tool.

## License

This script is provided as-is for creating ChannelIdentifiarr databases. The data retrieved belongs to Gracenote/TMS and is subject to their terms of service.

## Support

For issues or questions:
1. Check this README thoroughly
2. Verify your CSV file format
3. Try with a small test CSV first
4. Check the log output for specific error messages
