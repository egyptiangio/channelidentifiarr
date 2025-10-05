#!/usr/bin/env python3
"""
ChannelIdentifiarr Database Creation Script
Creates a comprehensive database of TV lineups and stations using Channels DVR API

Usage:
    python3 create_channelidentifiarr_db.py markets.csv

Requirements:
    - CSV file with markets (country,postal_code format)
    - Python 3.8+
    - Internet connection for API access

Architecture:
    - Multiple producer threads fetch from Channels DVR API in parallel
    - Single consumer thread writes to database sequentially
    - Queue-based communication eliminates database lock issues
"""

import argparse
import csv
import hashlib
import json
import logging
import queue
import requests
import shutil
import signal
import sqlite3
import sys
import time
import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Thread, Event, Lock
from typing import List, Dict, Optional, Set, Tuple

# ============================================
# CONFIGURATION
# ============================================

# Channels DVR API endpoint
CHANNELS_DVR_BASE_URL = "https://api.getchannels.com"

# Database and checkpoint paths
DB_PATH = Path("channelidentifiarr.db")
REGISTRY_PATH = Path("channelidentifiarr_registry.json")

# Worker configuration
DEFAULT_WORKERS = 4  # Optimal for ingestion phase
MAX_WORKERS = 10
ENHANCEMENT_WORKERS = 10  # For station enhancement phase
QUEUE_SIZE = 500

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================
# DATABASE SCHEMA CREATION
# ============================================

CREATE_SCHEMA_SQL = """
-- Markets table
CREATE TABLE IF NOT EXISTS markets (
    country TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    city TEXT,
    state TEXT,
    timezone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (country, postal_code)
);

-- Lineups table
CREATE TABLE IF NOT EXISTS lineups (
    lineup_id TEXT PRIMARY KEY,
    name TEXT,
    location TEXT,
    type TEXT,
    device TEXT,
    mso_id TEXT,
    mso_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stations table
CREATE TABLE IF NOT EXISTS stations (
    station_id TEXT PRIMARY KEY,
    name TEXT,
    call_sign TEXT,
    type TEXT,
    bcast_langs TEXT,
    logo_uri TEXT,
    logo_width INTEGER,
    logo_height INTEGER,
    logo_category TEXT,
    logo_primary BOOLEAN,
    source TEXT DEFAULT 'base',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Station-Lineup relationships
CREATE TABLE IF NOT EXISTS station_lineups (
    station_id TEXT NOT NULL,
    lineup_id TEXT NOT NULL,
    channel_number TEXT,
    affiliate_id TEXT,
    affiliate_call_sign TEXT,
    signal_type TEXT,
    video_type TEXT,
    tru_resolution TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (station_id, lineup_id),
    FOREIGN KEY (station_id) REFERENCES stations(station_id),
    FOREIGN KEY (lineup_id) REFERENCES lineups(lineup_id)
);

-- Lineup-Market relationships
CREATE TABLE IF NOT EXISTS lineup_markets (
    lineup_id TEXT NOT NULL,
    country TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (lineup_id, country, postal_code),
    FOREIGN KEY (lineup_id) REFERENCES lineups(lineup_id),
    FOREIGN KEY (country, postal_code) REFERENCES markets(country, postal_code)
);

-- Metadata table
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Processing log
CREATE TABLE IF NOT EXISTS processing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_type TEXT NOT NULL,
    target_id TEXT,
    status TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Database indexes (applied at the end)
CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_lineups_type ON lineups(type);
CREATE INDEX IF NOT EXISTS idx_lineup_markets_market ON lineup_markets(country, postal_code);
CREATE INDEX IF NOT EXISTS idx_lineup_markets_lineup ON lineup_markets(lineup_id);
CREATE INDEX IF NOT EXISTS idx_station_lineups_station ON station_lineups(station_id);
CREATE INDEX IF NOT EXISTS idx_station_lineups_lineup ON station_lineups(lineup_id);
CREATE INDEX IF NOT EXISTS idx_markets_country ON markets(country);
CREATE INDEX IF NOT EXISTS idx_processing_log_type ON processing_log(process_type);
CREATE INDEX IF NOT EXISTS idx_processing_log_target ON processing_log(target_id);
CREATE INDEX IF NOT EXISTS idx_station_lineups_composite ON station_lineups(station_id, lineup_id);
CREATE INDEX IF NOT EXISTS idx_lineup_markets_composite ON lineup_markets(lineup_id, country);
CREATE INDEX IF NOT EXISTS idx_stations_name_lower ON stations(LOWER(name));
CREATE INDEX IF NOT EXISTS idx_stations_call_lower ON stations(LOWER(call_sign));
CREATE INDEX IF NOT EXISTS idx_lineup_markets_country ON lineup_markets(country);
CREATE INDEX IF NOT EXISTS idx_lineup_markets_postal ON lineup_markets(postal_code);
"""

# ============================================
# DATA CLASSES
# ============================================

class MessageType(Enum):
    """Queue message types"""
    MARKET_DATA = "market_data"
    STATION_ENHANCEMENT = "station_enhancement"
    ERROR = "error"
    SHUTDOWN = "shutdown"


@dataclass
class QueueMessage:
    """Message passed through queue from producers to consumer"""
    msg_type: MessageType
    data: any
    market_index: Optional[int] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None


@dataclass
class Market:
    """Market information"""
    country: str
    postal_code: str
    city: Optional[str] = None
    state: Optional[str] = None
    timezone: Optional[str] = None


@dataclass
class Lineup:
    """Lineup information"""
    lineup_id: str
    name: Optional[str] = None
    location: Optional[str] = None
    type: Optional[str] = None
    device: Optional[str] = None
    mso_id: Optional[str] = None
    mso_name: Optional[str] = None


@dataclass
class Station:
    """Station information"""
    station_id: str
    call_sign: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    bcast_langs: Optional[str] = None
    logo_uri: Optional[str] = None
    logo_width: Optional[int] = None
    logo_height: Optional[int] = None
    logo_category: Optional[str] = None
    logo_primary: Optional[bool] = None
    source: str = 'base'


@dataclass
class LineupMarket:
    """Maps lineups to markets"""
    lineup_id: str
    country: str
    postal_code: str


@dataclass
class StationLineup:
    """Station-lineup relationship with channel info"""
    station_id: str
    lineup_id: str
    channel_number: str
    affiliate_id: Optional[str] = None
    affiliate_call_sign: Optional[str] = None
    signal_type: Optional[str] = None
    video_type: Optional[str] = None
    tru_resolution: Optional[str] = None


# ============================================
# CHECKPOINT MANAGER
# ============================================

class CheckpointManager:
    """Multi-CSV checkpoint registry system - tracks progress for resumability"""

    def __init__(self, registry_path: Path, force_refresh: bool = False, csv_path: Optional[Path] = None):
        self.registry_path = registry_path
        self.force_refresh = force_refresh
        self.csv_path = csv_path
        self.csv_hash = None
        self._lock = Lock()

        # Load or create registry
        self.registry = self._load_registry()

        # Get checkpoint for current CSV if provided
        if csv_path:
            self.csv_hash = self._calculate_file_hash(csv_path)
            self.starting_fresh = False
            self.data = self._get_or_create_checkpoint()
        else:
            self.data = self._create_empty_checkpoint()

    def _load_registry(self) -> dict:
        """Load or create checkpoint registry"""
        if self.registry_path.exists():
            with open(self.registry_path, 'r') as f:
                try:
                    registry = json.load(f)
                    if 'csv_files' not in registry and 'processed_markets' in registry:
                        logger.info("Found old checkpoint format, creating new registry")
                        return {'csv_files': {}, 'version': '1.0'}
                    return registry
                except json.JSONDecodeError:
                    logger.warning("Invalid registry file, creating new one")
                    return {'csv_files': {}, 'version': '1.0'}
        return {'csv_files': {}, 'version': '1.0'}

    def _get_or_create_checkpoint(self) -> dict:
        """Get existing checkpoint or create new one for current CSV"""
        if self.csv_hash in self.registry['csv_files']:
            checkpoint = self.registry['csv_files'][self.csv_hash]

            if checkpoint.get('status') == 'completed':
                if self.force_refresh:
                    logger.info(f"CSV {self.csv_path.name} was completed, force refreshing...")
                    self.starting_fresh = True
                    return self._create_empty_checkpoint()
                else:
                    logger.info(f"CSV {self.csv_path.name} was already completed, starting fresh...")
                    self.starting_fresh = True
                    return self._create_empty_checkpoint()

            logger.info(f"Resuming CSV {self.csv_path.name} from line {checkpoint['last_market_index'] + 1}")
            logger.info(f"  Started: {checkpoint['started_at']}")
            logger.info(f"  Markets processed: {len(checkpoint.get('processed_markets', []))}")
            return checkpoint

        logger.info(f"New CSV file: {self.csv_path.name} (hash: {self.csv_hash[:8]}...)")
        self.starting_fresh = True
        return self._create_empty_checkpoint()

    def _create_empty_checkpoint(self) -> dict:
        """Create empty checkpoint structure"""
        checkpoint = {
            'processed_markets': [],
            'failed_markets': [],
            'last_market_index': -1,
            'enhanced_stations': [],
            'phase': 'ingestion',
            'status': 'in_progress',
            'stats': {
                'total_stations': 0,
                'total_lineups': 0,
                'total_relationships': 0,
                'total_enhanced': 0,
                'total_markets': 0
            },
            'started_at': datetime.utcnow().isoformat(),
            'force_refresh': self.force_refresh
        }

        if self.csv_path and self.csv_path.exists():
            with open(self.csv_path, 'r') as f:
                total_lines = sum(1 for _ in f)

            checkpoint['csv_file'] = {
                'path': str(self.csv_path),
                'filename': self.csv_path.name,
                'hash': self.csv_hash or self._calculate_file_hash(self.csv_path),
                'size': self.csv_path.stat().st_size,
                'total_lines': total_lines,
                'modified': self.csv_path.stat().st_mtime
            }

        return checkpoint

    def _calculate_file_hash(self, file_path: Path, chunk_size: int = 8192) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def save(self):
        """Save checkpoint data to registry (thread-safe)"""
        with self._lock:
            self.data['last_updated'] = datetime.utcnow().isoformat()

            if self.csv_hash:
                self.registry['csv_files'][self.csv_hash] = self.data

            registry_copy = copy.deepcopy(self.registry)

        with open(self.registry_path, 'w') as f:
            json.dump(registry_copy, f, indent=2)

    def mark_market_processed(self, country: str, postal_code: str, index: int):
        """Mark a market as processed (thread-safe)"""
        with self._lock:
            market_key = f"{country}/{postal_code}"
            if market_key not in self.data['processed_markets']:
                self.data['processed_markets'].append(market_key)
            self.data['last_market_index'] = max(self.data['last_market_index'], index)

    def mark_market_failed(self, country: str, postal_code: str, error: str):
        """Mark a market as failed (thread-safe)"""
        with self._lock:
            market_key = f"{country}/{postal_code}"
            self.data['failed_markets'].append({
                'market': market_key,
                'error': error,
                'timestamp': datetime.utcnow().isoformat()
            })
        self.save()

    def is_market_processed(self, country: str, postal_code: str) -> bool:
        """Check if market has been processed (thread-safe)"""
        with self._lock:
            market_key = f"{country}/{postal_code}"
            return market_key in self.data['processed_markets']

    def update_stats(self, stations: int = 0, lineups: int = 0, relationships: int = 0, markets: int = 0):
        """Update running statistics (thread-safe)"""
        with self._lock:
            self.data['stats']['total_stations'] += stations
            self.data['stats']['total_lineups'] += lineups
            self.data['stats']['total_relationships'] += relationships
            self.data['stats']['total_markets'] += markets
        self.save()

    def mark_station_enhanced(self, station_id: str):
        """Mark a station as enhanced (thread-safe)"""
        with self._lock:
            if 'enhanced_stations' not in self.data:
                self.data['enhanced_stations'] = []
            if station_id not in self.data['enhanced_stations']:
                self.data['enhanced_stations'].append(station_id)
                self.data['stats']['total_enhanced'] = len(self.data['enhanced_stations'])

    def mark_completed(self):
        """Mark current CSV as completed in registry"""
        if self.csv_hash and self.csv_hash in self.registry['csv_files']:
            self.data['status'] = 'completed'
            self.data['completed_at'] = datetime.utcnow().isoformat()
            self.save()
            logger.info(f"Marked {self.csv_path.name} as completed")
            return True
        return False

    def archive(self):
        """Archive entire registry after successful completion"""
        if self.registry_path.exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_path = self.registry_path.with_name(f'registry_snapshot_{timestamp}.json')
            shutil.copy(str(self.registry_path), str(archive_path))
            logger.info(f"Registry snapshot saved to {archive_path}")
            return archive_path
        return None


# ============================================
# DATABASE MANAGER
# ============================================

class DatabaseManager:
    """Database operations - single threaded"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        # Optimized PRAGMA settings for better performance
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 30000")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        self.conn.execute("PRAGMA temp_store = MEMORY")
        self.conn.execute("PRAGMA mmap_size = 268435456")  # 256MB memory map

    def create_schema(self):
        """Create database schema"""
        self.conn.executescript(CREATE_SCHEMA_SQL)
        self.conn.commit()

    def create_indexes(self):
        """Create all indexes for optimal query performance"""
        logger.info("Creating database indexes...")
        self.conn.executescript(CREATE_INDEXES_SQL)
        self.conn.commit()
        logger.info("Database indexes created successfully")

    def insert_market(self, market: Market) -> bool:
        """Insert or update market"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO markets (country, postal_code, city, state, timezone)
            VALUES (?, ?, ?, ?, ?)
        """, (market.country, market.postal_code, market.city, market.state, market.timezone))
        return cursor.rowcount > 0

    def insert_lineup(self, lineup: Lineup, force: bool = False) -> bool:
        """Insert lineup"""
        cursor = self.conn.cursor()
        if force:
            cursor.execute("""
                INSERT OR REPLACE INTO lineups
                (lineup_id, name, location, type, device, mso_id, mso_name, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (lineup.lineup_id, lineup.name, lineup.location,
                  lineup.type, lineup.device, lineup.mso_id, lineup.mso_name))
        else:
            cursor.execute("""
                INSERT OR IGNORE INTO lineups
                (lineup_id, name, location, type, device, mso_id, mso_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (lineup.lineup_id, lineup.name, lineup.location,
                  lineup.type, lineup.device, lineup.mso_id, lineup.mso_name))
        return cursor.rowcount > 0

    def insert_lineup_market(self, lineup_market: LineupMarket, force: bool = False) -> bool:
        """Map lineup to market"""
        cursor = self.conn.cursor()
        if force:
            cursor.execute("""
                INSERT OR REPLACE INTO lineup_markets (lineup_id, country, postal_code)
                VALUES (?, ?, ?)
            """, (lineup_market.lineup_id, lineup_market.country, lineup_market.postal_code))
        else:
            cursor.execute("""
                INSERT OR IGNORE INTO lineup_markets (lineup_id, country, postal_code)
                VALUES (?, ?, ?)
            """, (lineup_market.lineup_id, lineup_market.country, lineup_market.postal_code))
        return cursor.rowcount > 0

    def insert_station(self, station: Station, force: bool = False) -> bool:
        """Insert or update station"""
        cursor = self.conn.cursor()
        if force:
            cursor.execute("""
                INSERT OR REPLACE INTO stations
                (station_id, call_sign, name, type, bcast_langs,
                 logo_uri, logo_width, logo_height, logo_category, logo_primary,
                 source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (station.station_id, station.call_sign, station.name, station.type,
                  station.bcast_langs, station.logo_uri,
                  station.logo_width, station.logo_height, station.logo_category,
                  station.logo_primary, station.source))
        else:
            cursor.execute("""
                INSERT OR IGNORE INTO stations
                (station_id, call_sign, name, type, bcast_langs,
                 logo_uri, logo_width, logo_height, logo_category, logo_primary, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (station.station_id, station.call_sign, station.name, station.type,
                  station.bcast_langs, station.logo_uri,
                  station.logo_width, station.logo_height, station.logo_category,
                  station.logo_primary, station.source))
        return cursor.rowcount > 0

    def insert_station_lineup(self, station_lineup: StationLineup, force: bool = False) -> bool:
        """Insert station-lineup relationship"""
        cursor = self.conn.cursor()
        if force:
            cursor.execute("""
                INSERT OR REPLACE INTO station_lineups
                (station_id, lineup_id, channel_number, affiliate_id, affiliate_call_sign,
                 signal_type, video_type, tru_resolution, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (station_lineup.station_id, station_lineup.lineup_id,
                  station_lineup.channel_number, station_lineup.affiliate_id,
                  station_lineup.affiliate_call_sign, station_lineup.signal_type,
                  station_lineup.video_type, station_lineup.tru_resolution))
        else:
            cursor.execute("""
                INSERT OR IGNORE INTO station_lineups
                (station_id, lineup_id, channel_number, affiliate_id, affiliate_call_sign,
                 signal_type, video_type, tru_resolution)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (station_lineup.station_id, station_lineup.lineup_id,
                  station_lineup.channel_number, station_lineup.affiliate_id,
                  station_lineup.affiliate_call_sign, station_lineup.signal_type,
                  station_lineup.video_type, station_lineup.tru_resolution))
        return cursor.rowcount > 0

    def get_processed_markets(self) -> Set[str]:
        """Get set of processed markets"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT country, postal_code FROM lineup_markets")
        return {f"{row[0]}/{row[1]}" for row in cursor.fetchall()}

    def get_stations_to_enhance(self) -> List[tuple]:
        """Get stations that need enhancement - returns (station_id, call_sign) tuples"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT station_id, call_sign FROM stations WHERE source = 'base'")
        return [(row[0], row[1]) for row in cursor.fetchall()]

    def update_station_enhancement(self, station: Station) -> bool:
        """Update station with enhanced data"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE stations
            SET name = ?, type = ?, bcast_langs = ?,
                logo_uri = ?, logo_width = ?, logo_height = ?,
                logo_category = ?, logo_primary = ?,
                source = 'enhanced', updated_at = CURRENT_TIMESTAMP
            WHERE station_id = ?
        """, (station.name, station.type, station.bcast_langs,
              station.logo_uri, station.logo_width, station.logo_height,
              station.logo_category, station.logo_primary, station.station_id))
        return cursor.rowcount > 0

    def clear_market_lineups(self, country: str, postal_code: str):
        """Clear lineups for a market (for force refresh)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM lineup_markets
            WHERE country = ? AND postal_code = ?
        """, (country, postal_code))
        return cursor.rowcount

    def update_metadata(self, key: str, value: str):
        """Update metadata"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, value))

    def commit(self):
        """Commit transaction"""
        self.conn.commit()

    def close(self):
        """Close connection"""
        self.conn.close()


# ============================================
# API FETCHER (PRODUCER)
# ============================================

class APIFetcher:
    """Fetches data from Channels DVR API - runs in producer threads"""

    def __init__(self):
        self.session = requests.Session()

    def normalize_postal_code(self, country: str, postal_code: str) -> str:
        """Normalize postal codes based on country"""
        country = country.upper()

        if country == 'USA':
            digits_only = ''.join(c for c in postal_code if c.isdigit())
            return digits_only[:5] if len(digits_only) >= 5 else digits_only.zfill(5)

        elif country == 'CAN':
            cleaned = postal_code.replace(' ', '').replace('-', '').upper()
            return cleaned[:3] if len(cleaned) >= 3 else cleaned

        elif country == 'GBR':
            cleaned = ' '.join(postal_code.upper().split())

            if ' ' in cleaned:
                return cleaned.split()[0]
            else:
                cleaned = cleaned.replace(' ', '')

                for i in range(2, min(5, len(cleaned))):
                    if i < len(cleaned) and cleaned[i].isdigit():
                        remaining = cleaned[i:]
                        if len(remaining) >= 3:
                            return cleaned[:i]

                if len(cleaned) <= 4:
                    return cleaned
                elif len(cleaned) > 4 and cleaned[2].isdigit():
                    return cleaned[:3]
                else:
                    return cleaned[:4]

        return postal_code

    def fetch_market_data(self, country: str, postal_code: str, market_index: int,
                          force_refresh: bool = False) -> QueueMessage:
        """Fetch all data for a market and return as queue message"""
        try:
            country = country.upper()
            normalized_postal = self.normalize_postal_code(country, postal_code)

            # Channels DVR API endpoint
            url = f"{CHANNELS_DVR_BASE_URL}/tms/lineups/{country}/{normalized_postal}"

            response = self.session.get(url, timeout=30)

            if response.status_code != 200:
                return QueueMessage(
                    msg_type=MessageType.ERROR,
                    data=f"Failed to fetch lineups: HTTP {response.status_code}",
                    market_index=market_index,
                    country=country,
                    postal_code=postal_code
                )

            lineups_data = response.json()
            if not lineups_data:
                return QueueMessage(
                    msg_type=MessageType.ERROR,
                    data="No lineups found",
                    market_index=market_index,
                    country=country,
                    postal_code=postal_code
                )

            # Prepare market data
            market = Market(country=country, postal_code=postal_code)

            # Process each lineup and fetch channels
            all_lineups = []
            all_stations = []
            all_relationships = []
            all_lineup_markets = []

            for lineup_data in lineups_data:
                lineup_id = lineup_data.get('lineupId')
                if not lineup_id:
                    continue

                # Create lineup
                mso = lineup_data.get('mso', {})
                lineup = Lineup(
                    lineup_id=lineup_id,
                    name=lineup_data.get('name', ''),
                    location=lineup_data.get('location'),
                    type=lineup_data.get('type'),
                    device=lineup_data.get('device'),
                    mso_id=mso.get('id') if mso else None,
                    mso_name=mso.get('name') if mso else None
                )
                all_lineups.append(lineup)

                # Create lineup-market mapping
                lineup_market = LineupMarket(
                    lineup_id=lineup_id,
                    country=country,
                    postal_code=postal_code
                )
                all_lineup_markets.append(lineup_market)

                # Fetch channels for this lineup
                channels_url = f"{CHANNELS_DVR_BASE_URL}/dvr/guide/stations/{lineup_id}"

                try:
                    channels_response = self.session.get(channels_url, timeout=30)
                    if channels_response.status_code == 200:
                        channels = channels_response.json()

                        for channel in channels:
                            station_id = channel.get('stationId')
                            if not station_id:
                                continue

                            # Create station
                            pref_image = channel.get('preferredImage', {})
                            station = Station(
                                station_id=station_id,
                                call_sign=channel.get('callSign'),
                                logo_uri=pref_image.get('uri') if pref_image else None,
                                logo_width=int(pref_image.get('width', 0)) if pref_image.get('width') else None,
                                logo_height=int(pref_image.get('height', 0)) if pref_image.get('height') else None,
                                logo_category=pref_image.get('category') if pref_image else None,
                                logo_primary=pref_image.get('primary') == 'true' if pref_image else None,
                                source='base'
                            )
                            all_stations.append(station)

                            # Create station-lineup relationship
                            video_quality = channel.get('videoQuality', {})
                            station_lineup = StationLineup(
                                station_id=station_id,
                                lineup_id=lineup_id,
                                channel_number=str(channel.get('channel', '')),
                                affiliate_id=channel.get('affiliateId'),
                                affiliate_call_sign=channel.get('affiliateCallSign'),
                                signal_type=video_quality.get('signalType'),
                                video_type=video_quality.get('videoType'),
                                tru_resolution=video_quality.get('truResolution')
                            )
                            all_relationships.append(station_lineup)
                except Exception as e:
                    logger.debug(f"Error fetching channels for {lineup_id}: {e}")

            # Return successful result
            return QueueMessage(
                msg_type=MessageType.MARKET_DATA,
                data={
                    'market': market,
                    'lineups': all_lineups,
                    'stations': all_stations,
                    'lineup_markets': all_lineup_markets,
                    'station_lineups': all_relationships,
                    'force_refresh': force_refresh
                },
                market_index=market_index,
                country=country,
                postal_code=postal_code
            )

        except Exception as e:
            return QueueMessage(
                msg_type=MessageType.ERROR,
                data=str(e),
                market_index=market_index,
                country=country,
                postal_code=postal_code
            )

    def fetch_station_details(self, station_id: str, call_sign: Optional[str] = None) -> Optional[Dict]:
        """Fetch enhanced station details using call sign lookup"""
        if not call_sign:
            logger.debug(f"No call sign available for station {station_id}")
            return None

        url = f"{CHANNELS_DVR_BASE_URL}/tms/stations/{call_sign}"

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    # Search for exact station ID match
                    for station in data:
                        if station.get('stationId') == station_id:
                            return station
                    logger.debug(f"No matching station_id in {len(data)} results for {call_sign}")
                return None
            else:
                logger.debug(f"Failed to fetch station details for {call_sign}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching station details for {call_sign}: {e}")
            return None


# ============================================
# DATABASE WRITER (CONSUMER)
# ============================================

class DatabaseWriter(Thread):
    """Consumes queue messages and writes to database - single thread"""

    def __init__(self, db_path: Path, checkpoint: CheckpointManager,
                 data_queue: queue.Queue, stop_event: Event):
        super().__init__(name="DatabaseWriter")
        self.db_path = db_path
        self.checkpoint = checkpoint
        self.data_queue = data_queue
        self.stop_event = stop_event
        self.stats = {
            'stations_added': 0,
            'lineups_added': 0,
            'relationships_added': 0,
            'markets_processed': 0,
            'markets_failed': 0,
            'stations_enhanced': 0
        }
        self.db = None
        self.BATCH_SIZE = 200
        self.pending_commits = 0
        self.last_commit_time = time.time()
        self.pending_checkpoints = []
        self.pending_enhancement_checkpoints = []
        self.pending_enhancement_commits = 0

    def run(self):
        """Main consumer loop"""
        logger.info("Database writer thread started")

        self.db = DatabaseManager(self.db_path)

        while True:
            if self.stop_event.is_set() and self.data_queue.empty():
                break

            try:
                msg = self.data_queue.get(timeout=0.5)

                if msg.msg_type == MessageType.SHUTDOWN:
                    logger.info("Database writer received shutdown signal")
                    self.stop_event.set()
                    break

                elif msg.msg_type == MessageType.MARKET_DATA:
                    self._process_market_data(msg)

                elif msg.msg_type == MessageType.STATION_ENHANCEMENT:
                    self._process_station_enhancement(msg)

                elif msg.msg_type == MessageType.ERROR:
                    self._process_error(msg)

                self.data_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Database writer error: {e}")

        # Final commit
        if self.pending_commits > 0 or self.pending_enhancement_commits > 0:
            if self.pending_commits > 0:
                logger.info(f"Flushing final batch: {self.pending_commits} pending market commits")
            if self.pending_enhancement_commits > 0:
                logger.info(f"Flushing final batch: {self.pending_enhancement_commits} pending enhancement commits")

            self.db.commit()

            for cp_info in self.pending_checkpoints:
                self.checkpoint.mark_market_processed(cp_info['country'], cp_info['postal_code'], cp_info['market_index'])
                self.checkpoint.update_stats(
                    stations=cp_info['stations'],
                    lineups=cp_info['lineups'],
                    relationships=cp_info['relationships'],
                    markets=1
                )
                self.stats['markets_processed'] += 1

            for station_id in self.pending_enhancement_checkpoints:
                self.checkpoint.mark_station_enhanced(station_id)
        else:
            self.db.commit()

        self.checkpoint.save()
        self.db.close()
        logger.info("Database writer thread stopped")

    def _process_market_data(self, msg: QueueMessage):
        """Process market data from queue"""
        data = msg.data
        country = msg.country
        postal_code = msg.postal_code
        market_index = msg.market_index
        force_refresh = data.get('force_refresh', False)

        if force_refresh:
            deleted = self.db.clear_market_lineups(country, postal_code)
            if deleted > 0:
                logger.info(f"Force refresh: cleared {deleted} lineup mappings for {country}/{postal_code}")

        # Insert market
        market = data['market']
        if market:
            self.db.insert_market(market)

        # Process lineups
        lineups_added = 0
        for lineup in data['lineups']:
            if self.db.insert_lineup(lineup, force=force_refresh):
                lineups_added += 1
                self.stats['lineups_added'] += 1

        # Process lineup-market mappings
        for lineup_market in data['lineup_markets']:
            self.db.insert_lineup_market(lineup_market, force=force_refresh)

        # Process stations
        stations_added = set()
        for station in data['stations']:
            if self.db.insert_station(station, force=force_refresh):
                stations_added.add(station.station_id)
                self.stats['stations_added'] += 1

        # Process station-lineup relationships
        relationships_added = 0
        for rel in data['station_lineups']:
            if self.db.insert_station_lineup(rel, force=force_refresh):
                relationships_added += 1
                self.stats['relationships_added'] += 1

        # Store checkpoint update info
        checkpoint_info = {
            'country': country,
            'postal_code': postal_code,
            'market_index': market_index,
            'stations': len(stations_added),
            'lineups': lineups_added,
            'relationships': relationships_added
        }
        self.pending_checkpoints.append(checkpoint_info)

        # Batch commit logic
        self.pending_commits += 1
        current_time = time.time()

        if self.pending_commits >= self.BATCH_SIZE or (current_time - self.last_commit_time) > 60:
            self.db.commit()
            logger.info(f"Batch commit: {self.pending_commits} markets to database")

            for cp_info in self.pending_checkpoints:
                self.checkpoint.mark_market_processed(cp_info['country'], cp_info['postal_code'], cp_info['market_index'])
                self.checkpoint.update_stats(
                    stations=cp_info['stations'],
                    lineups=cp_info['lineups'],
                    relationships=cp_info['relationships'],
                    markets=1
                )
                self.stats['markets_processed'] += 1

            self.pending_checkpoints = []
            self.pending_commits = 0
            self.last_commit_time = current_time
            self.checkpoint.save()
        else:
            self.stats['markets_processed'] += 1

        logger.info(f"Completed {country}/{postal_code}: {len(stations_added)} stations, "
                   f"{lineups_added} lineups, {relationships_added} relationships")

    def _process_station_enhancement(self, msg: QueueMessage):
        """Process station enhancement data"""
        station = msg.data
        if self.db.update_station_enhancement(station):
            self.stats['stations_enhanced'] += 1
            self.pending_enhancement_checkpoints.append(station.station_id)
            self.pending_enhancement_commits += 1

            if self.pending_enhancement_commits >= 200:
                self.db.commit()
                logger.info(f"Batch commit: {self.pending_enhancement_commits} station enhancements")

                for station_id in self.pending_enhancement_checkpoints:
                    self.checkpoint.mark_station_enhanced(station_id)

                self.pending_enhancement_checkpoints = []
                self.pending_enhancement_commits = 0
                self.checkpoint.save()

    def _process_error(self, msg: QueueMessage):
        """Process error message"""
        logger.error(f"Market {msg.country}/{msg.postal_code} failed: {msg.data}")
        self.checkpoint.mark_market_failed(msg.country, msg.postal_code, str(msg.data))
        self.stats['markets_failed'] += 1


# ============================================
# MAIN INGESTER
# ============================================

class ChannelIdentifiarrIngester:
    """Main ingester with producer-consumer architecture"""

    def __init__(self, markets_csv_path: Path, force_refresh: bool = False,
                 db_path: Path = DB_PATH, registry_path: Path = REGISTRY_PATH,
                 num_workers: int = DEFAULT_WORKERS):
        self.markets_csv_path = markets_csv_path
        self.force_refresh = force_refresh
        self.num_workers = min(num_workers, MAX_WORKERS)

        self.db_path = db_path
        self.checkpoint = CheckpointManager(registry_path, force_refresh, markets_csv_path)
        self.data_queue = queue.Queue(maxsize=QUEUE_SIZE)
        self.stop_event = Event()

        # Create database and schema
        temp_db = DatabaseManager(db_path)
        temp_db.create_schema()
        temp_db.update_metadata('last_run', datetime.utcnow().isoformat())
        temp_db.update_metadata('force_refresh', str(force_refresh))
        temp_db.commit()

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Start database writer thread
        self.db_writer = DatabaseWriter(db_path, self.checkpoint, self.data_queue, self.stop_event)
        self.db_writer.start()

        # Sync checkpoint with database if resuming
        if not force_refresh and not self.checkpoint.starting_fresh:
            db_markets = temp_db.get_processed_markets()
            synced = self.sync_checkpoint_with_db(db_markets)
            if synced > 0:
                logger.info(f"Synced {synced} markets from database to checkpoint")

        temp_db.close()
        self.db = None

    def _signal_handler(self, signum, frame):
        """Handle interrupt signals gracefully"""
        if not self.stop_event.is_set():
            logger.info("\n\nReceived interrupt signal. Shutting down gracefully...")
            self.stop_event.set()
            try:
                self.data_queue.put_nowait(QueueMessage(msg_type=MessageType.SHUTDOWN, data=None))
            except:
                pass
            return
        else:
            logger.info("Force quitting...")
            import os
            os._exit(1)

    def sync_checkpoint_with_db(self, db_markets: Set[str]) -> int:
        """Sync checkpoint with markets found in database"""
        checkpoint_markets = set(self.checkpoint.data['processed_markets'])
        missing_in_checkpoint = db_markets - checkpoint_markets

        if missing_in_checkpoint:
            logger.info(f"Found {len(missing_in_checkpoint)} markets in DB not in checkpoint")
            self.checkpoint.data['processed_markets'].extend(missing_in_checkpoint)
            self.checkpoint.save()
            return len(missing_in_checkpoint)
        return 0

    def run(self, skip_enhancement: bool = False, enhance_only: bool = False):
        """Main execution loop"""
        logger.info("=" * 60)
        logger.info("ChannelIdentifiarr Database Creation")
        logger.info(f"CSV: {self.markets_csv_path}")
        logger.info(f"Force refresh: {self.force_refresh}")
        logger.info(f"API workers: {self.num_workers}")
        if enhance_only:
            logger.info("Mode: Enhancement only")
        logger.info("=" * 60)

        # If enhance_only, skip to enhancement
        if enhance_only:
            logger.info("Skipping ingestion phase, running enhancement only")
            self.enhance_stations()
            self._shutdown_writer()
            return

        # Check if resuming enhancement phase
        if self.checkpoint.data.get('phase') == 'enhancement':
            logger.info("Resuming enhancement phase")
            self.enhance_stations()
            self._shutdown_writer()
            return

        # Read markets from CSV
        markets = []
        with open(self.markets_csv_path, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    markets.append((row[0], row[1]))

        total_markets = len(markets)
        logger.info(f"Found {total_markets} markets to process")

        # Resume from checkpoint
        start_index = self.checkpoint.data['last_market_index'] + 1
        if start_index > 0 and not self.force_refresh:
            logger.info(f"Resuming from market {start_index}")

        # Filter markets to process
        markets_to_process = []
        for i in range(start_index, total_markets):
            country, postal_code = markets[i]
            if not self.force_refresh:
                if self.checkpoint.is_market_processed(country, postal_code):
                    continue
            markets_to_process.append((i, country, postal_code))

        if not markets_to_process:
            logger.info("No markets to process")
        else:
            logger.info(f"Processing {len(markets_to_process)} markets")
            self._process_markets_parallel(markets_to_process)

        # Wait for queue to be processed
        interrupted_by_user = False
        if not self.stop_event.is_set():
            logger.info("Waiting for database writer to finish...")
            self.data_queue.join()
        else:
            interrupted_by_user = True

        # Run enhancement phase unless skipped or interrupted
        if not interrupted_by_user and not skip_enhancement:
            logger.info("Starting enhancement phase...")
            self.enhance_stations()
            if self.stop_event.is_set():
                interrupted_by_user = True
        elif skip_enhancement:
            logger.info("Skipping enhancement phase as requested")

        # Shutdown database writer
        logger.info("Shutting down...")
        self.stop_event.set()

        try:
            self.data_queue.put(QueueMessage(msg_type=MessageType.SHUTDOWN, data=None), timeout=1)
        except:
            pass

        self.db_writer.join(timeout=10)
        if self.db_writer.is_alive():
            logger.warning("Database writer thread did not stop cleanly")

        # Create indexes now that all data is loaded
        if not interrupted_by_user:
            logger.info("Creating database indexes (this may take a few minutes)...")
            temp_db = DatabaseManager(self.db_path)
            temp_db.create_indexes()
            temp_db.update_metadata('last_completed', datetime.utcnow().isoformat())
            temp_db.update_metadata('stats', json.dumps(self.db_writer.stats))
            temp_db.commit()
            temp_db.close()

            self.checkpoint.mark_completed()

            logger.info("Database creation complete!")

        # Final stats
        if interrupted_by_user:
            logger.info("\nIngestion interrupted by user")
        else:
            logger.info("=" * 60)
            logger.info("Ingestion Summary")
            logger.info(f"Markets processed: {self.db_writer.stats['markets_processed']}")
            logger.info(f"Markets failed: {self.db_writer.stats['markets_failed']}")
            logger.info(f"Stations added: {self.db_writer.stats['stations_added']}")
            logger.info(f"Lineups added: {self.db_writer.stats['lineups_added']}")
            logger.info(f"Relationships added: {self.db_writer.stats['relationships_added']}")
            logger.info(f"Stations enhanced: {self.db_writer.stats['stations_enhanced']}")

    def _process_markets_parallel(self, markets_to_process: List[Tuple[int, str, str]]):
        """Process markets using parallel API fetchers"""
        start_time = time.time()
        total_markets = len(markets_to_process)

        market_index = 0
        index_lock = Lock()
        completed_count = 0
        completed_lock = Lock()

        def worker_task(worker_id: int, fetcher: APIFetcher):
            nonlocal market_index, completed_count

            while not self.stop_event.is_set():
                with index_lock:
                    if market_index >= total_markets:
                        break
                    current_index = market_index
                    market_index += 1

                i, country, postal_code = markets_to_process[current_index]

                try:
                    result = fetcher.fetch_market_data(country, postal_code, i, self.force_refresh)

                    if not self.stop_event.is_set():
                        self.data_queue.put(result)

                    with completed_lock:
                        completed_count += 1
                        if completed_count % 100 == 0 and not self.stop_event.is_set():
                            elapsed = time.time() - start_time
                            rate = completed_count / elapsed if elapsed > 0 else 0
                            remaining = (total_markets - completed_count) / rate if rate > 0 else 0
                            logger.info(f"Progress: {completed_count}/{total_markets} "
                                      f"({completed_count*100/total_markets:.1f}%), "
                                      f"Rate: {rate:.1f} markets/sec, ETA: {remaining/60:.1f} min")

                except Exception as e:
                    if not self.stop_event.is_set():
                        logger.error(f"Error processing market {i} ({country}/{postal_code}): {e}")
                        error_msg = QueueMessage(
                            msg_type=MessageType.ERROR,
                            data=str(e),
                            market_index=i,
                            country=country,
                            postal_code=postal_code
                        )
                        self.data_queue.put(error_msg)

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            api_fetchers = [APIFetcher() for _ in range(self.num_workers)]

            futures = []
            for worker_id in range(self.num_workers):
                future = executor.submit(worker_task, worker_id, api_fetchers[worker_id])
                futures.append(future)

            logger.info(f"Started {self.num_workers} API workers to process {total_markets} markets")

            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    if not self.stop_event.is_set():
                        logger.error(f"Worker thread error: {e}")

        logger.info(f"Market processing complete: {completed_count}/{total_markets} processed")

    def _shutdown_writer(self):
        """Helper method to properly shutdown the database writer thread"""
        logger.info("Shutting down...")
        self.stop_event.set()

        try:
            self.data_queue.put(QueueMessage(msg_type=MessageType.SHUTDOWN, data=None), timeout=1)
        except:
            pass

        self.db_writer.join(timeout=10)
        if self.db_writer.is_alive():
            logger.warning("Database writer thread did not stop cleanly")
        else:
            logger.info("Database writer thread stopped cleanly")

    def enhance_stations(self):
        """Enhancement phase - fetch detailed station info"""
        logger.info("Starting station enhancement phase...")

        self.checkpoint.data['phase'] = 'enhancement'
        self.checkpoint.save()

        # Get stations to enhance
        temp_db = DatabaseManager(self.db_path)
        stations_to_enhance = temp_db.get_stations_to_enhance()
        temp_db.close()

        # Filter out already enhanced stations
        enhanced_already = set(self.checkpoint.data.get('enhanced_stations', []))
        stations_to_enhance = [s for s in stations_to_enhance if s not in enhanced_already]

        if not stations_to_enhance:
            logger.info("All stations already enhanced")
            return

        total_stations = len(stations_to_enhance)
        logger.info(f"Enhancing {total_stations} stations with {ENHANCEMENT_WORKERS} parallel workers...")

        def fetch_and_queue_station(station_id: str, call_sign: Optional[str], fetcher: APIFetcher):
            try:
                station_data = fetcher.fetch_station_details(station_id, call_sign)
                if station_data:
                    pref_image = station_data.get('preferredImage', {})
                    station = Station(
                        station_id=station_id,
                        call_sign=station_data.get('callSign'),
                        name=station_data.get('name'),
                        type=station_data.get('type'),
                        bcast_langs=json.dumps(station_data.get('bcastLangs', [])),
                        logo_uri=pref_image.get('uri'),
                        logo_width=int(pref_image.get('width', 0)) if pref_image.get('width') else None,
                        logo_height=int(pref_image.get('height', 0)) if pref_image.get('height') else None,
                        logo_category=pref_image.get('category'),
                        logo_primary=pref_image.get('primary') == 'true',
                        source='enhanced'
                    )

                    msg = QueueMessage(
                        msg_type=MessageType.STATION_ENHANCEMENT,
                        data=station
                    )
                    self.data_queue.put(msg)
                    return True
            except Exception as e:
                logger.debug(f"Error enhancing station {station_id}: {e}")
            return False

        # Process stations in parallel
        start_time = time.time()
        station_index = 0
        index_lock = Lock()
        completed = 0
        completed_lock = Lock()

        def enhance_worker(worker_id: int, fetcher: APIFetcher):
            nonlocal station_index, completed

            while not self.stop_event.is_set():
                with index_lock:
                    if station_index >= total_stations:
                        break
                    current_index = station_index
                    station_index += 1

                station_id, call_sign = stations_to_enhance[current_index]

                fetch_and_queue_station(station_id, call_sign, fetcher)

                with completed_lock:
                    completed += 1
                    if completed % 500 == 0 and not self.stop_event.is_set():
                        elapsed = time.time() - start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        remaining = (total_stations - completed) / rate if rate > 0 else 0
                        logger.info(f"Enhancement progress: {completed}/{total_stations} "
                                  f"({completed*100/total_stations:.1f}%), "
                                  f"Rate: {rate:.1f} stations/sec, ETA: {remaining/60:.1f} min")

        with ThreadPoolExecutor(max_workers=ENHANCEMENT_WORKERS) as executor:
            api_fetchers = [APIFetcher() for _ in range(ENHANCEMENT_WORKERS)]

            futures = []
            for worker_id in range(ENHANCEMENT_WORKERS):
                future = executor.submit(enhance_worker, worker_id, api_fetchers[worker_id])
                futures.append(future)

            logger.info(f"Started {ENHANCEMENT_WORKERS} workers to enhance {total_stations} stations")

            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    if not self.stop_event.is_set():
                        logger.error(f"Enhancement worker error: {e}")

        self.data_queue.join()
        elapsed = time.time() - start_time
        if not self.stop_event.is_set():
            logger.info(f"Enhanced {self.db_writer.stats['stations_enhanced']} stations in {elapsed/60:.1f} minutes")


# ============================================
# MAIN ENTRY POINT
# ============================================

def main():
    parser = argparse.ArgumentParser(
        description='ChannelIdentifiarr Database Creation Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard database creation with default 4 workers
  python3 create_channelidentifiarr_db.py usa_markets.csv

  # Use 6 workers for faster processing
  python3 create_channelidentifiarr_db.py usa_markets.csv --workers 6

  # Force refresh all data
  python3 create_channelidentifiarr_db.py usa_markets.csv --force

  # Skip enhancement phase (base data only)
  python3 create_channelidentifiarr_db.py usa_markets.csv --skip-enhancement

  # Run only enhancement phase on existing database
  python3 create_channelidentifiarr_db.py usa_markets.csv --enhance-only

This script creates a comprehensive database of TV lineups and stations
using the Channels DVR public API. The database includes:
  - Markets (countries and postal codes)
  - Lineups (TV providers in each market)
  - Stations (TV channels with logos and metadata)
  - Relationships between stations and lineups
  - Optimized indexes for fast queries
        """
    )

    parser.add_argument(
        'markets_csv',
        help='Path to CSV file containing markets (country,postal_code)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force refresh all data even if already in database'
    )

    parser.add_argument(
        '--skip-enhancement',
        action='store_true',
        help='Skip the station enhancement phase'
    )

    parser.add_argument(
        '--enhance-only',
        action='store_true',
        help='Skip ingestion and run only the enhancement phase'
    )

    parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Keep checkpoint file after successful completion'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=DEFAULT_WORKERS,
        help=f'Number of parallel API workers (default: {DEFAULT_WORKERS}, max: {MAX_WORKERS})'
    )

    args = parser.parse_args()

    # Validate conflicting flags
    if args.skip_enhancement and args.enhance_only:
        logger.error("Cannot use both --skip-enhancement and --enhance-only flags")
        sys.exit(1)

    # Validate CSV file
    markets_csv_path = Path(args.markets_csv)
    if not markets_csv_path.exists():
        logger.error(f"CSV file not found: {markets_csv_path}")
        sys.exit(1)

    # Validate worker count
    num_workers = min(max(1, args.workers), MAX_WORKERS)
    if args.workers != num_workers:
        logger.warning(f"Worker count adjusted to {num_workers} (valid range: 1-{MAX_WORKERS})")

    # Run ingestion
    try:
        ingester = ChannelIdentifiarrIngester(
            markets_csv_path=markets_csv_path,
            force_refresh=args.force,
            num_workers=num_workers
        )
        ingester.run(skip_enhancement=args.skip_enhancement, enhance_only=args.enhance_only)

        # Archive checkpoint if requested
        if not args.no_cleanup and ingester.checkpoint.data.get('status') == 'completed':
            ingester.checkpoint.archive()

    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
