#!/usr/bin/env python3
"""
Channel Identifiarr Web Application
Backend API server for channel management
"""

from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
import sqlite3
import os
from pathlib import Path
import logging
import requests
import json
from datetime import datetime, timedelta
import re
from difflib import SequenceMatcher
from settings_manager import get_settings_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Database configuration
DB_PATH = os.environ.get('DATABASE_PATH', '/data/channelidentifiarr.db')

# Check if database exists
DB_EXISTS = os.path.exists(DB_PATH)
if not DB_EXISTS:
    logger.warning(f"Database not found at {DB_PATH} - running in no-database mode")
else:
    logger.info(f"Database found at {DB_PATH}")

# Dispatcharr configuration - will be received from frontend
# Token management per connection
dispatcharr_sessions = {}

# Settings manager
settings_manager = get_settings_manager()

def get_db_connection():
    """Create a database connection with row factory"""
    if not DB_EXISTS:
        raise Exception("Database not available")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        # Test the connection
        conn.execute("SELECT 1")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        # Try without row factory
        conn = sqlite3.connect(DB_PATH)
        return conn

def dict_from_row(row):
    """Convert SQLite Row to dictionary"""
    return dict(zip(row.keys(), row))

def parse_channel_name(channel_name):
    """
    Parse channel name to extract country, resolution, and clean name.
    Port of the bash channel_parsing.sh logic.
    """
    clean_name = channel_name.upper()
    detected_country = ""
    detected_resolution = ""

    # Step 0: Handle special character separators
    # Replace special separators with spaces
    separators = r'[\|★◉:►▶→»≫—–=〉〈⟩⟨◆♦◊⬥●•]'
    if re.search(separators, clean_name):
        clean_name = re.sub(separators, ' ', clean_name)
        clean_name = ' '.join(clean_name.split())  # Normalize spaces

    # Helper function to check word boundaries
    def word_exists(text, word):
        pattern = r'\b' + re.escape(word) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))

    def remove_word(text, word):
        pattern = r'\b' + re.escape(word) + r'\b'
        text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
        return ' '.join(text.split())

    # Step 1: Country detection
    country_patterns = {
        'USA': ['US', 'USA', 'UNITED STATES'],
        'GBR': ['UK', 'GBR', 'BRITAIN', 'ENGLAND'],
        'CAN': ['CA', 'CAN', 'CANADA'],
        'AUS': ['AU', 'AUS', 'AUSTRALIA'],
        'DEU': ['DE', 'DEU', 'GERMANY', 'DEUTSCH'],
        'FRA': ['FR', 'FRA', 'FRANCE', 'FRENCH'],
        'ITA': ['IT', 'ITA', 'ITALY', 'ITALIAN'],
        'ESP': ['ES', 'ESP', 'SPAIN', 'SPANISH'],
        'NLD': ['NL', 'NLD', 'NETHERLANDS', 'DUTCH'],
        'BEL': ['BE', 'BEL', 'BELGIUM', 'BELGIAN'],
        'CHE': ['CH', 'CHE', 'SWITZERLAND', 'SWISS'],
        'AUT': ['AT', 'AUT', 'AUSTRIA', 'AUSTRIAN'],
        'SWE': ['SE', 'SWE', 'SWEDEN', 'SWEDISH'],
        'NOR': ['NO', 'NOR', 'NORWAY', 'NORWEGIAN'],
        'DNK': ['DK', 'DNK', 'DENMARK', 'DANISH'],
        'FIN': ['FI', 'FIN', 'FINLAND', 'FINNISH'],
        'JPN': ['JP', 'JPN', 'JAPAN', 'JAPANESE'],
        'KOR': ['KR', 'KOR', 'KOREA', 'KOREAN'],
        'CHN': ['CN', 'CHN', 'CHINA', 'CHINESE'],
        'IND': ['IN', 'IND', 'INDIA', 'INDIAN'],
        'BRA': ['BR', 'BRA', 'BRAZIL', 'BRAZILIAN'],
        'MEX': ['MX', 'MEX', 'MEXICO', 'MEXICAN'],
        'ARG': ['AR', 'ARG', 'ARGENTINA', 'ARGENTINIAN'],
    }

    for country_code, patterns in country_patterns.items():
        for pattern in patterns:
            if word_exists(clean_name, pattern):
                detected_country = country_code
                clean_name = remove_word(clean_name, pattern)
                break
        if detected_country:
            break

    # Step 2: Resolution detection
    if any(word_exists(clean_name, x) for x in ['4K', 'UHD', 'UHDTV']) or re.search(r'Ultra\s*HD', clean_name, re.IGNORECASE):
        detected_resolution = 'UHDTV'
        for term in ['4K', 'UHD', 'UHDTV']:
            clean_name = remove_word(clean_name, term)
        clean_name = re.sub(r'Ultra\s*HD', ' ', clean_name, flags=re.IGNORECASE)
    elif word_exists(clean_name, 'FHD') or re.search(r'\b(1080[ip]?|720[ip]?)\b', clean_name):
        detected_resolution = 'HDTV'
        clean_name = remove_word(clean_name, 'FHD')
        clean_name = re.sub(r'\b(1080[ip]?|720[ip]?)\b', ' ', clean_name)
    elif word_exists(clean_name, 'HD') and not re.search(r'\d', clean_name):
        detected_resolution = 'HDTV'
        clean_name = remove_word(clean_name, 'HD')
    elif word_exists(clean_name, 'SD') or re.search(r'\b480[ip]?\b', clean_name):
        detected_resolution = 'SDTV'
        clean_name = remove_word(clean_name, 'SD')
        clean_name = re.sub(r'\b480[ip]?\b', ' ', clean_name)

    # Step 3: General cleanup
    # Remove common prefixes
    clean_name = re.sub(r'^(CHANNEL|CH|NETWORK|NET|TV|TELEVISION|DIGITAL|CABLE|SATELLITE|STREAM|LIVE|24/7|24-7)\s+', '', clean_name, flags=re.IGNORECASE)

    # Remove common suffixes
    clean_name = re.sub(r'\s+(CHANNEL|CH|NETWORK|NET|TV|TELEVISION|DIGITAL|LIVE|STREAM|PLUS|\+|24/7|24-7)$', '', clean_name, flags=re.IGNORECASE)

    # Remove special characters
    clean_name = clean_name.replace('_', ' ').replace('-', ' ')
    clean_name = re.sub(r'[(){}\[\]<>#@$%^&*]', '', clean_name)
    clean_name = re.sub(r'[^\w\s]$', '', clean_name)  # Remove trailing punctuation

    # Remove generic terms
    generic_terms = ['THE', 'A', 'AN', 'AND', 'OR', 'OF', 'IN', 'ON', 'AT', 'TO', 'FOR',
                     'WITH', 'OFFICIAL', 'ORIGINAL', 'PREMIUM', 'EXCLUSIVE', 'ONLINE',
                     'DIGITAL', 'STREAMING', 'BROADCAST']
    for term in generic_terms:
        clean_name = remove_word(clean_name, term)

    # Final cleanup
    clean_name = ' '.join(clean_name.split())

    # Return to original case for clean name
    if clean_name:
        # Try to preserve original casing pattern
        original_words = channel_name.split()
        clean_words = clean_name.split()
        if len(original_words) > 0 and len(clean_words) > 0:
            # Simple heuristic: if original was mixed case, use title case
            if channel_name != channel_name.upper() and channel_name != channel_name.lower():
                clean_name = clean_name.title()
            elif channel_name == channel_name.lower():
                clean_name = clean_name.lower()

    result = {
        'clean_name': clean_name or channel_name,
        'country': detected_country,
        'resolution': detected_resolution,
        'original': channel_name
    }
    logger.info(f"Parsed '{channel_name}' -> {result}")
    return result

def calculate_match_score(channel_name, station_data, parsed_channel=None):
    """Calculate match score between channel and station"""
    if not parsed_channel:
        parsed_channel = parse_channel_name(channel_name)

    clean_channel = parsed_channel['clean_name'].upper()
    station_name = (station_data.get('name') or '').upper()
    call_sign = (station_data.get('call_sign') or '').upper()

    # Calculate similarity scores
    name_score = SequenceMatcher(None, clean_channel, station_name).ratio()
    call_sign_score = SequenceMatcher(None, clean_channel, call_sign).ratio() if call_sign else 0

    # Bonus for exact matches
    if clean_channel == station_name:
        name_score = 1.0
    if clean_channel == call_sign:
        call_sign_score = 1.0

    # Take the best score
    base_score = max(name_score, call_sign_score)

    # Apply bonuses/penalties
    score = base_score

    # Bonus for resolution match (if detected) - HIGH PRIORITY
    if parsed_channel.get('resolution'):
        video_types = station_data.get('video_types', '')
        if video_types and parsed_channel['resolution'] in video_types:
            score += 0.15
        elif video_types and parsed_channel['resolution'] not in video_types:
            # Penalty for resolution mismatch
            score -= 0.2

    # Bonus for country match (if detected)
    if parsed_channel.get('country') and station_data.get('country') == parsed_channel['country']:
        score += 0.1

    # Bonus for having a logo
    if station_data.get('logo_uri'):
        score += 0.05

    return min(max(score, 0.0), 1.0)  # Cap between 0.0 and 1.0

@app.route('/')
def serve_frontend():
    """Serve the frontend application"""
    # If no database, serve the setup page
    if not DB_EXISTS:
        return serve_setup_page()

    frontend_path = os.path.join(os.path.dirname(__file__), 'frontend', 'index.html')
    if os.path.exists(frontend_path):
        with open(frontend_path, 'r') as f:
            return f.read()
    else:
        # Return the HTML directly if file not found
        return '''<!DOCTYPE html>
<html>
<head><title>Channel Identifiarr</title></head>
<body>
    <h1>Channel Identifiarr Web</h1>
    <p>Frontend not found at expected path. API is working.</p>
    <p>Try: <a href="/api/health">/api/health</a></p>
</body>
</html>'''

def serve_setup_page():
    """Serve the initial setup page when no database is available"""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Channel Identifiarr - Setup Required</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 700px;
            width: 100%;
            padding: 40px;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
        }

        .logo {
            font-size: 48px;
            margin-bottom: 10px;
        }

        h1 {
            color: #1e3c72;
            font-size: 32px;
            margin-bottom: 10px;
        }

        .subtitle {
            color: #666;
            font-size: 16px;
        }

        .status-box {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 20px;
            margin: 25px 0;
            border-radius: 4px;
        }

        .status-box h2 {
            color: #2e7d32;
            font-size: 20px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
        }

        .status-box h2::before {
            content: "✓";
            display: inline-block;
            margin-right: 10px;
            font-size: 24px;
        }

        .warning-box {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 20px;
            margin: 25px 0;
            border-radius: 4px;
        }

        .warning-box h2 {
            color: #e65100;
            font-size: 20px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
        }

        .warning-box h2::before {
            content: "⚠";
            display: inline-block;
            margin-right: 10px;
            font-size: 24px;
        }

        .info-section {
            margin: 25px 0;
        }

        .info-section h3 {
            color: #1e3c72;
            font-size: 18px;
            margin-bottom: 15px;
        }

        .info-section p {
            color: #333;
            line-height: 1.6;
            margin-bottom: 10px;
        }

        .steps {
            background: #f5f5f5;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }

        .steps ol {
            margin-left: 20px;
        }

        .steps li {
            color: #333;
            line-height: 1.8;
            margin-bottom: 10px;
        }

        .code-block {
            background: #263238;
            color: #aed581;
            padding: 15px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            overflow-x: auto;
            margin: 15px 0;
        }

        .footer {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        }

        .highlight {
            background: #fff59d;
            padding: 2px 6px;
            border-radius: 3px;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">📺</div>
            <h1>Channel Identifiarr Web</h1>
            <p class="subtitle">Setup Required</p>
        </div>

        <div class="status-box">
            <h2>Installation Successful!</h2>
            <p>Channel Identifiarr Web is running correctly. The application is ready to use once you provide a database.</p>
        </div>

        <div class="warning-box">
            <h2>Database Not Found</h2>
            <p>Most functionality requires a Gracenote station database. The database file was not found at the expected location.</p>
        </div>

        <div class="info-section">
            <h3>What You Need</h3>
            <p>Channel Identifiarr requires a SQLite database containing Gracenote station data with TV stations, logos, and lineup information.</p>
            <p>This database is <strong>not included</strong> with the installation and must be obtained separately.</p>
        </div>

        <div class="info-section">
            <h3>How to Get the Database</h3>
            <p>Contact the <span class="highlight">Dispatcharr</span> community to inquire about obtaining a compatible database file in the correct format.</p>
        </div>

        <div class="info-section">
            <h3>Installing the Database</h3>
            <div class="steps">
                <ol>
                    <li>Obtain a <code>channelidentifiarr.db</code> file from the Dispatcharr community</li>
                    <li>Create a data directory and place the database file inside:
                        <div class="code-block">mkdir -p /path/to/data<br>mv channelidentifiarr.db /path/to/data/</div>
                    </li>
                    <li>Update your <code>docker-compose.yml</code> to mount the data folder:
                        <div class="code-block">volumes:<br>  - /path/to/data:/data</div>
                    </li>
                    <li>Restart the container:
                        <div class="code-block">docker-compose restart</div>
                    </li>
                </ol>
            </div>
        </div>

        <div class="info-section">
            <h3>Database Requirements</h3>
            <p>The database must be a SQLite file with the following tables:</p>
            <ul style="margin-left: 20px; margin-top: 10px;">
                <li><code>stations</code> - TV station information</li>
                <li><code>lineups</code> - Lineup data</li>
                <li><code>station_lineups</code> - Station-lineup relationships</li>
                <li><code>lineup_markets</code> - Market information</li>
            </ul>
        </div>

        <div class="footer">
            <p><strong>Channel Identifiarr Web</strong> v0.3.2-alpha</p>
            <p>Part of the Dispatcharr ecosystem</p>
        </div>
    </div>
</body>
</html>'''

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM stations")
        count = cursor.fetchone()['count']
        conn.close()

        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'stations_count': count
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/database/metadata')
def get_database_metadata():
    """Get database metadata including version and date"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get metadata from metadata table
        cursor.execute("""
            SELECT key, value, updated_at
            FROM metadata
            WHERE key IN ('data_version', 'effective_date', 'schema_version', 'last_updated')
        """)

        metadata = {}
        for row in cursor.fetchall():
            row_dict = dict_from_row(row)
            metadata[row_dict['key']] = {
                'value': row_dict['value'],
                'updated_at': row_dict.get('updated_at')
            }

        # Get station count
        cursor.execute("SELECT COUNT(*) as count FROM stations")
        station_count = cursor.fetchone()['count']

        conn.close()

        return jsonify({
            'version': metadata.get('data_version', {}).get('value', 'Unknown'),
            'effective_date': metadata.get('effective_date', {}).get('value', 'Unknown'),
            'schema_version': metadata.get('schema_version', {}).get('value', 'Unknown'),
            'last_updated': metadata.get('last_updated', {}).get('value', 'Unknown'),
            'station_count': station_count
        })
    except Exception as e:
        logger.error(f"Error getting database metadata: {e}")
        return jsonify({
            'version': 'Unknown',
            'effective_date': 'Unknown',
            'schema_version': 'Unknown',
            'last_updated': 'Unknown',
            'station_count': 0,
            'error': str(e)
        }), 500

@app.route('/api/search/stations', methods=['GET'])
def search_stations():
    """Search for stations in the database"""
    try:
        # Get search parameters
        query = request.args.get('q', '').strip()
        country = request.args.get('country', '').upper()
        station_type = request.args.get('type', '')
        quality = request.args.get('quality', '')
        limit = int(request.args.get('limit', 50))
        if limit == -1:  # -1 means unlimited
            limit = 0

        if not query:
            return jsonify({'error': 'Search query required'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Try FTS first, fallback to LIKE if it fails
        use_fts = True
        try:
            # Test if FTS is available
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='stations_fts'")
            has_fts = cursor.fetchone()[0] > 0

            if has_fts and not query.isdigit():
                # Use FTS for text search
                # Prepare query for FTS (simpler approach)
                fts_query = query
                cursor.execute("""
                    SELECT station_id FROM stations_fts
                    WHERE stations_fts MATCH ?
                    LIMIT 1
                """, (fts_query,))
                # If this works, FTS is good
                cursor.fetchone()
                station_filter = """s.station_id IN (
                    SELECT station_id FROM stations_fts
                    WHERE stations_fts MATCH ?
                )"""
                params = [fts_query]
            else:
                use_fts = False
        except Exception as e:
            logger.warning(f"FTS not available or failed: {e}")
            use_fts = False

        if not use_fts:
            # Fallback to traditional LIKE search
            station_filter = """s.station_id IN (
                SELECT station_id FROM stations
                WHERE LOWER(name) LIKE LOWER(?)
                   OR LOWER(call_sign) LIKE LOWER(?)
                   OR station_id = ?
            )"""
            params = [f'%{query}%', f'%{query}%', query]

        # Build the main query - ONE result per station with essential fields only
        sql = f"""
            SELECT DISTINCT
                s.station_id,
                s.name,
                s.call_sign,
                s.type,
                s.logo_uri
            FROM stations s
            LEFT JOIN station_lineups sl ON s.station_id = sl.station_id
            LEFT JOIN lineups l ON sl.lineup_id = l.lineup_id
            LEFT JOIN lineup_markets lm ON l.lineup_id = lm.lineup_id
            WHERE {station_filter}
        """

        # Add filters
        if country and country != 'ALL':
            sql += " AND lm.country = ?"
            params.append(country)

        if station_type and station_type != 'all':
            sql += " AND l.type = ?"
            params.append(station_type)

        if quality:
            # Treat UHDTV, 4k, and UHDTV/4K as equivalent
            if quality.upper() in ['UHDTV', '4K', 'UHDTV/4K']:
                sql += " AND (sl.video_type = 'UHDTV' OR sl.video_type = '4k')"
            else:
                sql += " AND sl.video_type = ?"
                params.append(quality)

        sql += """
            ORDER BY
                CASE
                    WHEN LOWER(s.name) = LOWER(?) THEN 1
                    WHEN LOWER(s.call_sign) = LOWER(?) THEN 2
                    WHEN LOWER(s.name) LIKE LOWER(?) THEN 3
                    ELSE 4
                END,
                s.name
        """
        params.extend([query, query, f'{query}%'])

        # Allow unlimited results if limit is 0
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Convert to list of dictionaries
        results = []
        for row in rows:
            result = dict_from_row(row)
            result['has_logo'] = bool(result.get('logo_uri'))
            results.append(result)

        conn.close()

        return jsonify({
            'query': query,
            'count': len(results),
            'results': results
        })

    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/station/<station_id>')
def get_station_details(station_id):
    """Get detailed information about a specific station"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get station info
        cursor.execute("""
            SELECT * FROM stations WHERE station_id = ?
        """, (station_id,))

        station = cursor.fetchone()
        if not station:
            conn.close()
            return jsonify({'error': 'Station not found'}), 404

        station_dict = dict_from_row(station)

        # Get lineup count and video types
        cursor.execute("""
            SELECT
                COUNT(DISTINCT lineup_id) as lineup_count,
                GROUP_CONCAT(DISTINCT video_type) as video_types,
                MAX(affiliate_id) as affiliate_id,
                MAX(affiliate_call_sign) as affiliate_call_sign
            FROM station_lineups
            WHERE station_id = ?
        """, (station_id,))

        lineup_info = cursor.fetchone()
        if lineup_info:
            station_dict['lineup_count'] = lineup_info['lineup_count']
            station_dict['video_types'] = lineup_info['video_types']
            station_dict['affiliate_id'] = lineup_info['affiliate_id']
            station_dict['affiliate_call_sign'] = lineup_info['affiliate_call_sign']

        conn.close()

        return jsonify(station_dict)

    except Exception as e:
        logger.error(f"Station details error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_database_stats():
    """Get database statistics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        stats = {}

        # Total stations
        cursor.execute("SELECT COUNT(*) as count FROM stations")
        stats['total_stations'] = cursor.fetchone()['count']

        # Total countries
        cursor.execute("SELECT COUNT(DISTINCT country) as count FROM lineup_markets")
        stats['total_countries'] = cursor.fetchone()['count']

        # Total markets (postal codes)
        cursor.execute("SELECT COUNT(DISTINCT postal_code) as count FROM lineup_markets")
        stats['total_markets'] = cursor.fetchone()['count']

        # Total lineups
        cursor.execute("SELECT COUNT(*) as count FROM lineups")
        stats['total_lineups'] = cursor.fetchone()['count']

        # Stations with logos
        cursor.execute("""
            SELECT COUNT(*) as count FROM stations
            WHERE logo_uri IS NOT NULL AND logo_uri != ''
        """)
        stats['stations_with_logos'] = cursor.fetchone()['count']

        conn.close()

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/metadata')
def get_metadata():
    """Get available countries, lineup types, and video qualities for filters"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all countries
        cursor.execute("""
            SELECT DISTINCT country
            FROM lineup_markets
            WHERE country IS NOT NULL
            ORDER BY country
        """)
        countries = [row['country'] for row in cursor.fetchall()]

        # Get all lineup types
        cursor.execute("""
            SELECT DISTINCT type
            FROM lineups
            WHERE type IS NOT NULL
            ORDER BY type
        """)
        lineup_types = [row['type'] for row in cursor.fetchall()]

        # Get all video qualities - combine UHDTV and 4k into single entry
        cursor.execute("""
            SELECT DISTINCT video_type
            FROM station_lineups
            WHERE video_type IS NOT NULL AND LENGTH(video_type) > 0
            ORDER BY
                CASE
                    WHEN video_type = 'UHDTV' THEN 1
                    WHEN video_type = '4k' THEN 2
                    WHEN video_type = 'HDTV' THEN 3
                    WHEN video_type = 'SDTV' THEN 4
                    ELSE 5
                END,
                video_type
        """)
        raw_qualities = [row['video_type'] for row in cursor.fetchall()]

        # Combine UHDTV and 4k into single 'UHDTV/4K' entry
        qualities = []
        has_uhd = False
        for q in raw_qualities:
            if q.upper() in ['UHDTV', '4K']:
                if not has_uhd:
                    qualities.append('UHDTV/4K')
                    has_uhd = True
            else:
                qualities.append(q)

        conn.close()

        return jsonify({
            'countries': countries,
            'lineup_types': lineup_types,
            'qualities': qualities
        })

    except Exception as e:
        logger.error(f"Metadata error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# DISPATCHARR INTEGRATION
# ============================================================================

def get_dispatcharr_token(url, username, password):
    """Get valid Dispatcharr access token with JIT authentication"""
    global dispatcharr_sessions

    # Create session key
    session_key = f"{url}_{username}"

    # Get or create session
    if session_key not in dispatcharr_sessions:
        dispatcharr_sessions[session_key] = {
            'access_token': None,
            'refresh_token': None,
            'token_expiry': None
        }

    session = dispatcharr_sessions[session_key]

    # Check if we have a valid token
    if session['access_token'] and session['token_expiry']:
        if datetime.now() < session['token_expiry']:
            return session['access_token']

    # Try to refresh token if we have a refresh token
    if session['refresh_token']:
        try:
            response = requests.post(
                f"{url}/api/accounts/token/refresh/",
                json={'refresh': session['refresh_token']},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                session['access_token'] = data.get('access')
                # Token typically valid for 5 minutes, refresh at 4 minutes
                session['token_expiry'] = datetime.now() + timedelta(minutes=4)
                logger.info("Dispatcharr token refreshed successfully")
                return session['access_token']
        except Exception as e:
            logger.warning(f"Token refresh failed: {e}")

    # Full authentication
    try:
        auth_data = {
            'username': username,
            'password': password
        }
        logger.info(f"Authenticating to {url}/api/accounts/token/ with username: {username}")
        response = requests.post(
            f"{url}/api/accounts/token/",
            json=auth_data,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            session['access_token'] = data.get('access')
            session['refresh_token'] = data.get('refresh')
            session['token_expiry'] = datetime.now() + timedelta(minutes=4)
            logger.info("Dispatcharr authentication successful")
            return session['access_token']
        elif response.status_code == 401:
            logger.error(f"Dispatcharr authentication failed: Invalid credentials - {response.text}")
            return None
        elif response.status_code == 403:
            logger.error(f"Dispatcharr authentication failed: 403 Forbidden - {response.text}")
            return None
        else:
            logger.error(f"Dispatcharr authentication failed: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"Dispatcharr authentication error: {e}")
        return None

def dispatcharr_api_request(url, username, password, method, endpoint, data=None):
    """Make authenticated request to Dispatcharr API"""
    token = get_dispatcharr_token(url, username, password)
    if not token:
        return None, "Authentication failed"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    try:
        full_url = f"{url}{endpoint}"

        if method == 'GET':
            response = requests.get(full_url, headers=headers, timeout=30)
        elif method == 'POST':
            response = requests.post(full_url, headers=headers, json=data, timeout=30)
        elif method == 'PATCH':
            response = requests.patch(full_url, headers=headers, json=data, timeout=30)
        else:
            return None, f"Unsupported method: {method}"

        # Handle 401 and retry once
        if response.status_code == 401:
            logger.info("Token expired, refreshing...")
            # Clear token for this session
            session_key = f"{url}_{username}"
            if session_key in dispatcharr_sessions:
                dispatcharr_sessions[session_key]['access_token'] = None

            token = get_dispatcharr_token(url, username, password)
            if token:
                headers['Authorization'] = f'Bearer {token}'
                if method == 'GET':
                    response = requests.get(full_url, headers=headers, timeout=30)
                elif method == 'POST':
                    response = requests.post(full_url, headers=headers, json=data, timeout=30)
                elif method == 'PATCH':
                    response = requests.patch(full_url, headers=headers, json=data, timeout=30)

        if response.status_code in [200, 201, 204]:
            try:
                return response.json() if response.text else {}, None
            except:
                return response.text, None
        else:
            # Return detailed error from API response
            error_detail = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                error_detail = f"HTTP {response.status_code}: {json.dumps(error_data)}"
            except:
                if response.text:
                    error_detail = f"HTTP {response.status_code}: {response.text}"
            return None, error_detail

    except Exception as e:
        logger.error(f"Dispatcharr API request error: {e}")
        return None, str(e)

@app.route('/api/dispatcharr/test', methods=['POST'])
def test_dispatcharr_connection():
    """Test Dispatcharr connection"""
    try:
        creds = request.json
        url = creds.get('url')
        username = creds.get('username')
        password = creds.get('password')


        if not all([url, username, password]):
            return jsonify({'error': 'Missing credentials'}), 400

        # Try to authenticate
        token = get_dispatcharr_token(url, username, password)
        if token:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Authentication failed'}), 401

    except Exception as e:
        logger.error(f"Connection test error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dispatcharr/channels', methods=['POST'])
def get_dispatcharr_channels():
    """Get all channels from Dispatcharr"""
    try:
        # Get credentials from request
        creds = request.json
        url = creds.get('url')
        username = creds.get('username')
        password = creds.get('password')

        if not all([url, username, password]):
            return jsonify({'error': 'Missing credentials'}), 400

        # Get all channels (handle pagination)
        channels_data = []
        channels_url = '/api/channels/channels/'
        while channels_url:
            data, error = dispatcharr_api_request(url, username, password, 'GET', channels_url)
            if error:
                return jsonify({'error': error}), 500

            # Handle both paginated and non-paginated responses
            if isinstance(data, dict) and 'results' in data:
                channels_data.extend(data['results'])
                next_url = data.get('next')
                if next_url:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(next_url)
                    channels_url = f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path
                else:
                    channels_url = None
            elif isinstance(data, list):
                channels_data.extend(data)
                channels_url = None
            else:
                channels_url = None

        # Get groups for mapping
        groups_data, _ = dispatcharr_api_request(url, username, password, 'GET', '/api/channels/groups/')
        groups_map = {}
        if groups_data and isinstance(groups_data, list):
            for group in groups_data:
                groups_map[group.get('id')] = group.get('name', 'Unknown')

        # Get only logos assigned to channels (prevents timeout with 100k+ logo libraries)
        logo_ids = set()
        for ch in channels_data:
            logo_id = ch.get('logo_id')
            if logo_id:
                logo_ids.add(logo_id)

        logger.info(f"Fetching {len(logo_ids)} logos for {len(channels_data)} channels")

        logos_map = {}
        for logo_id in logo_ids:
            logo_data, _ = dispatcharr_api_request(url, username, password, 'GET', f'/api/channels/logos/{logo_id}/')
            if logo_data:
                logos_map[logo_id] = logo_data.get('url', '')

        # Process channels
        channels = []
        if channels_data and isinstance(channels_data, list):
            logger.info(f"Processing {len(channels_data)} channels with {len(groups_map)} groups and {len(logos_map)} logos")

            for ch in channels_data:
                # Extract the fields we need
                group_id = ch.get('channel_group_id')
                logo_id = ch.get('logo_id')

                channel = {
                    'id': ch.get('id'),
                    'channel_number': ch.get('channel_number', 0),
                    'name': ch.get('name'),
                    'call_sign': ch.get('tvg_id', ''),  # TVG ID is often used as call sign
                    'gracenote_id': ch.get('tvc_guide_stationid', ''),
                    'group_id': group_id,
                    'group_name': groups_map.get(group_id, f"Group {group_id}" if group_id else "Ungrouped"),
                    'logo_url': logos_map.get(logo_id, ''),
                    'enabled': ch.get('enabled', True)
                }
                channels.append(channel)

            # Sort channels by channel number
            channels.sort(key=lambda x: float(x['channel_number']) if x['channel_number'] else 9999)

        return jsonify({
            'channels': channels,
            'total': len(channels)
        })

    except Exception as e:
        logger.error(f"Error fetching Dispatcharr channels: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/match/suggest', methods=['POST'])
def suggest_matches():
    """Get suggested matches for a channel"""
    try:
        data = request.json
        channel_name = data.get('channel_name', '')
        channel_id = data.get('channel_id')
        existing_station_id = data.get('existing_station_id')

        if not channel_name:
            return jsonify({'error': 'Channel name required'}), 400

        # Parse the channel name
        parsed = parse_channel_name(channel_name)

        # Search for matches using cleaned name
        conn = get_db_connection()
        cursor = conn.cursor()

        # If there's an existing station_id, get that as a direct match first
        existing_match = None
        if existing_station_id:
            logger.info(f"Channel has existing Gracenote ID: {existing_station_id} - fetching direct match")
            cursor.execute("""
                SELECT DISTINCT
                    s.station_id,
                    s.name,
                    s.call_sign,
                    s.type,
                    s.logo_uri,
                    GROUP_CONCAT(DISTINCT lm.country) as countries,
                    GROUP_CONCAT(DISTINCT sl.video_type) as video_types
                FROM stations s
                LEFT JOIN station_lineups sl ON s.station_id = sl.station_id
                LEFT JOIN lineups l ON sl.lineup_id = l.lineup_id
                LEFT JOIN lineup_markets lm ON l.lineup_id = lm.lineup_id
                WHERE s.station_id = ?
                GROUP BY s.station_id, s.name, s.call_sign, s.type, s.logo_uri
            """, [existing_station_id])

            existing_row = cursor.fetchone()
            if existing_row:
                station = dict_from_row(existing_row)
                if station.get('countries'):
                    station['countries'] = station['countries'].split(',')
                else:
                    station['countries'] = []

                existing_match = {
                    'station': station,
                    'score': 1.0,  # Perfect match since it's the existing ID
                    'confidence': 'existing',
                    'is_existing': True
                }
                logger.info(f"Found existing station match: {station.get('name')} ({existing_station_id})")

        # Build search query
        clean_name = parsed['clean_name']
        detected_resolution = parsed.get('resolution', '')

        logger.info(f"Matching channel: '{channel_name}' | Clean: '{clean_name}' | Resolution: '{detected_resolution}'")

        # Try multiple search strategies with resolution filter
        sql = """
            SELECT DISTINCT
                s.station_id,
                s.name,
                s.call_sign,
                s.type,
                s.logo_uri,
                GROUP_CONCAT(DISTINCT lm.country) as countries,
                GROUP_CONCAT(DISTINCT sl.video_type) as video_types
            FROM stations s
            LEFT JOIN station_lineups sl ON s.station_id = sl.station_id
            LEFT JOIN lineups l ON sl.lineup_id = l.lineup_id
            LEFT JOIN lineup_markets lm ON l.lineup_id = lm.lineup_id
            WHERE (
                LOWER(s.name) LIKE LOWER(?)
                OR LOWER(s.call_sign) LIKE LOWER(?)
                OR LOWER(s.name) = LOWER(?)
                OR LOWER(s.call_sign) = LOWER(?)
            )
        """

        params = [
            f'%{clean_name}%', f'%{clean_name}%',
            clean_name, clean_name
        ]

        # Add resolution filter if detected
        if detected_resolution:
            logger.info(f"Filtering by resolution: {detected_resolution}")
            sql += " AND sl.video_type = ?"
            params.append(detected_resolution)
        else:
            logger.info("No resolution detected - showing all resolutions")

        sql += """
            GROUP BY s.station_id, s.name, s.call_sign, s.type, s.logo_uri
            ORDER BY
                CASE
                    WHEN LOWER(s.name) = LOWER(?) THEN 1
                    WHEN LOWER(s.call_sign) = LOWER(?) THEN 2
                    WHEN LOWER(s.name) LIKE LOWER(?) THEN 3
                    ELSE 4
                END
            LIMIT 20
        """

        params.extend([clean_name, clean_name, f'{clean_name}%'])

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Calculate scores and sort
        matches = []
        for row in rows:
            station = dict_from_row(row)

            # Split countries if present
            if station.get('countries'):
                station['countries'] = station['countries'].split(',')
            else:
                station['countries'] = []

            # Calculate match score
            score = calculate_match_score(channel_name, station, parsed)

            matches.append({
                'station': station,
                'score': score,
                'confidence': 'high' if score > 0.8 else 'medium' if score > 0.5 else 'low'
            })

        # Sort by score
        matches.sort(key=lambda x: x['score'], reverse=True)

        # Get top matches
        top_matches = matches[:5]

        # If we have an existing match, prepend it to the top
        if existing_match:
            # Remove existing_station_id from top_matches if it appears
            top_matches = [m for m in top_matches if m['station']['station_id'] != existing_station_id]
            # Prepend existing match at the top
            top_matches = [existing_match] + top_matches[:4]  # Keep total at 5

        conn.close()

        return jsonify({
            'channel_id': channel_id,
            'channel_name': channel_name,
            'parsed': parsed,
            'matches': top_matches,
            'total_found': len(matches),
            'has_existing': existing_match is not None
        })

    except Exception as e:
        logger.error(f"Error suggesting matches: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/match/apply', methods=['POST'])
def apply_match():
    """Apply a match to a Dispatcharr channel"""
    try:
        data = request.json
        channel_id = data.get('channel_id')
        station_id = data.get('station_id')
        dispatcharr_config = data.get('dispatcharr_config', {})
        apply_options = data.get('apply_options', {
            'applyStationId': True,
            'applyChannelName': False,
            'applyCallSign': False,
            'applyLogo': True
        })

        if not all([channel_id, station_id, dispatcharr_config]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Get station details
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT station_id, name, call_sign, type, logo_uri
            FROM stations
            WHERE station_id = ?
        """, [station_id])

        station = cursor.fetchone()
        if not station:
            conn.close()
            return jsonify({'error': 'Station not found'}), 404

        station_data = dict_from_row(station)
        conn.close()

        # Build update_data based on apply_options
        update_data = {}

        if apply_options.get('applyStationId', True):
            update_data['tvc_guide_stationid'] = station_data['station_id']

        if apply_options.get('applyChannelName', False):
            update_data['name'] = station_data['name']

        if apply_options.get('applyCallSign', False):
            update_data['tvg_id'] = station_data['call_sign'] or ''

        if apply_options.get('applyLogo', True) and station_data.get('logo_uri'):
            update_data['logo'] = station_data['logo_uri']

        # Ensure we're updating at least one field
        if not update_data:
            return jsonify({'error': 'No fields selected for update'}), 400

        # Make Dispatcharr API call
        result, error = dispatcharr_api_request(
            url=dispatcharr_config['url'],
            username=dispatcharr_config['username'],
            password=dispatcharr_config['password'],
            method='PATCH',
            endpoint=f'/api/channels/channels/{channel_id}/',
            data=update_data
        )

        if result and not error:
            return jsonify({
                'success': True,
                'channel': result,
                'station': station_data
            })
        else:
            return jsonify({'error': 'Failed to update channel'}), 500

    except Exception as e:
        logger.error(f"Error applying match: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/match/batch', methods=['POST'])
def batch_match_channels():
    """Start batch matching for multiple channels"""
    try:
        data = request.json
        channels = data.get('channels', [])

        if not channels:
            return jsonify({'error': 'No channels provided'}), 400

        # Process each channel
        results = []
        for channel in channels:
            try:
                # Parse channel name
                parsed = parse_channel_name(channel['name'])

                # Get suggestions (simplified version for batch)
                conn = get_db_connection()
                cursor = conn.cursor()

                clean_name = parsed['clean_name']

                cursor.execute("""
                    SELECT station_id, name, call_sign, logo_uri
                    FROM stations
                    WHERE LOWER(name) = LOWER(?)
                       OR LOWER(call_sign) = LOWER(?)
                    LIMIT 1
                """, [clean_name, clean_name])

                match = cursor.fetchone()
                conn.close()

                if match:
                    station = dict_from_row(match)
                    score = calculate_match_score(channel['name'], station, parsed)

                    results.append({
                        'channel': channel,
                        'parsed': parsed,
                        'suggested_match': station,
                        'score': score,
                        'status': 'matched' if score > 0.7 else 'review_needed'
                    })
                else:
                    results.append({
                        'channel': channel,
                        'parsed': parsed,
                        'suggested_match': None,
                        'score': 0,
                        'status': 'no_match'
                    })

            except Exception as e:
                results.append({
                    'channel': channel,
                    'error': str(e),
                    'status': 'error'
                })

        # Group by status
        matched = [r for r in results if r.get('status') == 'matched']
        review_needed = [r for r in results if r.get('status') == 'review_needed']
        no_match = [r for r in results if r.get('status') == 'no_match']
        errors = [r for r in results if r.get('status') == 'error']

        return jsonify({
            'total': len(channels),
            'matched': len(matched),
            'review_needed': len(review_needed),
            'no_match': len(no_match),
            'errors': len(errors),
            'results': results
        })

    except Exception as e:
        logger.error(f"Error in batch matching: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dispatcharr/channels/<channel_id>', methods=['PATCH'])
def update_dispatcharr_channel(channel_id):
    """Update a Dispatcharr channel"""
    try:
        data = request.json
        url = data.get('url')
        username = data.get('username')
        password = data.get('password')

        # Extract update data
        update_data = data.get('update_data', {})

        # Map our field names to Dispatcharr field names
        dispatcharr_data = {}
        if 'gracenote_id' in update_data:
            dispatcharr_data['tvc_guide_stationid'] = update_data['gracenote_id']
        if 'name' in update_data:
            dispatcharr_data['name'] = update_data['name']
        if 'call_sign' in update_data:
            dispatcharr_data['tvg_id'] = update_data['call_sign']
        if 'channel_number' in update_data:
            dispatcharr_data['channel_number'] = update_data['channel_number']
        if 'group_id' in update_data:
            dispatcharr_data['channel_group_id'] = update_data['group_id']

        if not all([url, username, password]):
            return jsonify({'error': 'Missing Dispatcharr credentials'}), 400

        result, error = dispatcharr_api_request(
            url=url,
            username=username,
            password=password,
            method='PATCH',
            endpoint=f'/api/channels/channels/{channel_id}/',
            data=dispatcharr_data
        )

        if result:
            return jsonify({'success': True, 'channel': result})
        else:
            return jsonify({'error': 'Failed to update channel'}), 500

    except Exception as e:
        logger.error(f"Error updating Dispatcharr channel: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dispatcharr/groups', methods=['POST'])
def get_dispatcharr_groups():
    """Get all Dispatcharr channel groups"""
    try:
        data = request.json
        url = data.get('url')
        username = data.get('username')
        password = data.get('password')

        if not all([url, username, password]):
            return jsonify({'error': 'Missing Dispatcharr credentials'}), 400

        groups_data, error = dispatcharr_api_request(url, username, password, 'GET', '/api/channels/groups/')

        if error:
            return jsonify({'error': error}), 500

        groups = []
        if groups_data and isinstance(groups_data, list):
            for group in groups_data:
                groups.append({
                    'id': group.get('id'),
                    'name': group.get('name', 'Unknown')
                })

        return jsonify({'groups': groups})

    except Exception as e:
        logger.error(f"Error fetching Dispatcharr groups: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dispatcharr/groups', methods=['PUT'])
def create_dispatcharr_group():
    """Create a new Dispatcharr channel group"""
    try:
        data = request.json
        url = data.get('url')
        username = data.get('username')
        password = data.get('password')
        group_name = data.get('name')

        if not all([url, username, password, group_name]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Create group with name and permissions (required by API)
        logger.info(f"Creating new group with name: {group_name}")
        group_data = {
            'name': group_name,
            'permissions': []  # Empty permissions array (required field)
        }

        create_result, create_error = dispatcharr_api_request(
            url=url,
            username=username,
            password=password,
            method='POST',
            endpoint='/api/accounts/groups/',
            data=group_data
        )

        if not create_result:
            error_msg = create_error or 'Failed to create group'
            logger.error(f"Failed to create group '{group_name}': {error_msg}")
            if 'pattern' in str(create_error).lower():
                error_msg = f"Invalid group name format: {create_error}"
            return jsonify({'error': error_msg}), 500

        logger.info(f"Group created successfully: {create_result.get('id')} - {create_result.get('name')}")

        return jsonify({
            'success': True,
            'group': {
                'id': create_result.get('id'),
                'name': create_result.get('name', group_name)
            }
        })

    except Exception as e:
        logger.error(f"Error creating Dispatcharr group: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# EMBY INTEGRATION ENDPOINTS
# ============================================================================

def emby_authenticate(url, username, password):
    """Authenticate with Emby server and return access token"""
    try:
        auth_url = f"{url}/emby/Users/AuthenticateByName"
        headers = {
            'Content-Type': 'application/json',
            'X-Emby-Authorization': 'MediaBrowser Client="ChannelIdentifiarr", Device="Web", DeviceId="channelidentifiarr", Version="0.3.2-alpha"'
        }
        auth_data = {
            'Username': username,
            'Pw': password
        }

        response = requests.post(auth_url, json=auth_data, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        return data.get('AccessToken'), data.get('User', {}).get('Id')
    except Exception as e:
        logger.error(f"Emby authentication error: {e}")
        return None, None

def emby_api_request(url, token, method='GET', endpoint='', data=None):
    """Make an API request to Emby server"""
    try:
        full_url = f"{url}{endpoint}"
        headers = {'X-Emby-Token': token}

        if method == 'GET':
            response = requests.get(full_url, headers=headers, timeout=15)
        elif method == 'POST':
            headers['Content-Type'] = 'application/json'
            response = requests.post(full_url, json=data, headers=headers, timeout=15)
        elif method == 'DELETE':
            response = requests.delete(full_url, headers=headers, timeout=15)
        else:
            return None, "Unsupported HTTP method"

        response.raise_for_status()

        # Some endpoints return empty responses
        if response.status_code == 204 or not response.text:
            return {}, None

        return response.json(), None
    except requests.exceptions.RequestException as e:
        logger.error(f"Emby API request error: {e}")
        return None, str(e)

@app.route('/api/emby/test', methods=['POST'])
def test_emby_connection():
    """Test Emby server connection"""
    try:
        data = request.json
        url = data.get('url', '').rstrip('/')
        username = data.get('username')
        password = data.get('password')

        if not url:
            return jsonify({'success': False, 'error': 'URL required'}), 400

        # Try to authenticate
        token, user_id = emby_authenticate(url, username, password)

        if not token:
            return jsonify({'success': False, 'error': 'Authentication failed'}), 401

        # Get server info
        result, error = emby_api_request(url, token, 'GET', '/emby/System/Info')

        if result:
            return jsonify({
                'success': True,
                'server_name': result.get('ServerName', 'Emby Server'),
                'version': result.get('Version', 'Unknown')
            })
        else:
            return jsonify({'success': False, 'error': error or 'Connection failed'}), 500

    except Exception as e:
        logger.error(f"Emby connection test error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/emby/channels', methods=['POST'])
def get_emby_channels():
    """Get all Emby Live TV channels"""
    try:
        data = request.json
        url = data.get('url', '').rstrip('/')
        username = data.get('username')
        password = data.get('password')

        token, user_id = emby_authenticate(url, username, password)

        if not token:
            return jsonify({'error': 'Authentication failed'}), 401

        # Get channels from management endpoint
        result, error = emby_api_request(url, token, 'GET', '/emby/LiveTv/Manage/Channels?Fields=ManagementId,ListingsId,Name,ChannelNumber,Id')

        if result:
            # Handle both array and object responses
            channels = result if isinstance(result, list) else result.get('Items', [])
            return jsonify({'channels': channels})
        else:
            return jsonify({'error': error or 'Failed to get channels'}), 500

    except Exception as e:
        logger.error(f"Error getting Emby channels: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/emby/scan-missing-listings', methods=['POST'])
def scan_emby_missing_listings():
    """Scan Emby channels for missing ListingsId and add providers with intelligent lineup selection"""
    try:
        data = request.json
        url = data.get('url', '').rstrip('/')
        username = data.get('username')
        password = data.get('password')
        user_country = data.get('country', '').strip().upper()  # Optional country preference
        user_zipcode = data.get('zipcode', '').strip()  # Optional ZIP code

        token, user_id = emby_authenticate(url, username, password)

        if not token:
            return jsonify({'error': 'Authentication failed'}), 401

        # Get channels
        result, error = emby_api_request(url, token, 'GET', '/emby/LiveTv/Manage/Channels?Fields=ManagementId,ListingsId,Name,ChannelNumber,Id')

        if not result:
            return jsonify({'error': error or 'Failed to get channels'}), 500

        channels = result if isinstance(result, list) else result.get('Items', [])

        # Find channels missing ListingsId
        missing_channels = [ch for ch in channels if not ch.get('ListingsId')]

        if not missing_channels:
            return jsonify({'providers_added': 0, 'message': 'All channels have ListingsId'}), 200

        # Extract station IDs from ManagementId
        station_ids = set()
        for ch in missing_channels:
            mgmt_id = ch.get('ManagementId', '')
            if mgmt_id and '_' in mgmt_id:
                station_id = mgmt_id.split('_')[-1]
                if station_id.isdigit() and len(station_id) >= 4:
                    station_ids.add(station_id)

        if not station_ids:
            return jsonify({'error': 'No valid station IDs found'}), 400

        # Look up stations in database with intelligent lineup selection
        if not DB_EXISTS:
            return jsonify({'error': 'Database not available'}), 503

        conn = get_db_connection()
        cursor = conn.cursor()

        # Strategy: Find minimum set of lineups that cover all stations
        # Build a map: station_id -> [available lineups]
        station_lineup_map = {}

        for station_id in station_ids:
            # Get ALL available lineups for this station, but prioritize based on user preferences
            # This ensures we can still cover international channels even with country/ZIP filters
            query_base = """
                SELECT sl.lineup_id, l.name as lineup_name, l.type, l.location
                FROM station_lineups sl
                JOIN lineups l ON sl.lineup_id = l.lineup_id
                WHERE sl.station_id = ?
            """

            params = [station_id]

            # Build ORDER BY to prioritize based on preferences
            order_parts = []

            # Prefer user's country if specified
            if user_country:
                order_parts.append(f"CASE WHEN l.lineup_id LIKE ? THEN 0 ELSE 1 END")
                params.append(f"{user_country}-%")

            # Prefer user's location if ZIP provided
            if user_zipcode:
                order_parts.append(f"CASE WHEN l.location LIKE ? THEN 0 ELSE 1 END")
                params.append(f"%{user_zipcode}%")

            # Always prioritize by lineup type
            order_parts.append("""
                CASE l.type
                    WHEN 'OTA' THEN 1
                    WHEN 'CABLE' THEN 2
                    WHEN 'SATELLITE' THEN 3
                    WHEN 'VMVPD' THEN 4
                    ELSE 5
                END
            """)

            query = query_base + " ORDER BY " + ", ".join(order_parts)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            if rows:
                station_lineup_map[station_id] = [
                    {
                        'lineup_id': row[0] if isinstance(row, tuple) else row['lineup_id'],
                        'lineup_name': row[1] if isinstance(row, tuple) else row['lineup_name'],
                        'type': row[2] if isinstance(row, tuple) else row['type'],
                        'location': row[3] if isinstance(row, tuple) else row['location']
                    }
                    for row in rows
                ]

        # Greedy algorithm to find minimum set of lineups for complete coverage
        uncovered_stations = set(station_lineup_map.keys())
        selected_lineups = {}  # lineup_id -> {name, country, stations_covered}

        while uncovered_stations:
            # Find lineup that covers the most uncovered stations
            best_lineup = None
            best_coverage = []

            # Count how many uncovered stations each lineup covers
            lineup_coverage = {}
            for station_id in uncovered_stations:
                for lineup_info in station_lineup_map.get(station_id, []):
                    lineup_id = lineup_info['lineup_id']
                    if lineup_id not in lineup_coverage:
                        lineup_coverage[lineup_id] = {
                            'stations': [],
                            'info': lineup_info
                        }
                    lineup_coverage[lineup_id]['stations'].append(station_id)

            if not lineup_coverage:
                break

            # Select lineup with maximum coverage
            best_lineup_id = max(lineup_coverage.keys(), key=lambda x: len(lineup_coverage[x]['stations']))
            best_lineup_info = lineup_coverage[best_lineup_id]['info']
            covered_stations = lineup_coverage[best_lineup_id]['stations']

            # Extract country from lineup_id (first 3 chars before dash)
            country = best_lineup_id.split('-')[0] if '-' in best_lineup_id else 'USA'

            selected_lineups[best_lineup_id] = {
                'name': best_lineup_info['lineup_name'],
                'country': country,
                'type': best_lineup_info['type'],
                'stations_covered': len(covered_stations)
            }

            # Remove covered stations
            uncovered_stations -= set(covered_stations)

        conn.close()

        if not selected_lineups:
            return jsonify({'error': 'No lineups found for the specified stations'}), 404

        # Add listing providers to Emby with SSE progress
        def generate():
            providers_added = 0
            providers_failed = 0
            total_lineups = len(selected_lineups)
            current = 0

            for lineup_id, lineup_info in selected_lineups.items():
                current += 1

                # Send progress update
                yield f"data: {json.dumps({'progress': current, 'total': total_lineups, 'lineup': lineup_info['name'], 'lineup_id': lineup_id})}\n\n"

                provider_data = {
                    'ListingsId': lineup_id,
                    'Type': 'embygn',
                    'Country': lineup_info['country'],
                    'Name': lineup_info['name']
                }

                result, error = emby_api_request(url, token, 'POST', '/emby/LiveTv/ListingProviders', provider_data)

                if result is not None:  # Success includes empty dict
                    providers_added += 1
                else:
                    providers_failed += 1
                    logger.warning(f"Failed to add provider {lineup_id}: {error}")

            # Send completion
            completion_data = {
                'done': True,
                'providers_added': providers_added,
                'providers_failed': providers_failed,
                'total_stations': len(station_ids),
                'lineups_selected': list(selected_lineups.keys())
            }
            yield f"data: {json.dumps(completion_data)}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        logger.error(f"Error scanning Emby listings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/emby/delete-logos', methods=['POST'])
def delete_emby_logos():
    """Delete all channel logos from Emby with SSE progress updates"""
    try:
        data = request.json
        url = data.get('url', '').rstrip('/')
        username = data.get('username')
        password = data.get('password')

        token, user_id = emby_authenticate(url, username, password)

        if not token:
            return jsonify({'error': 'Authentication failed'}), 401

        # Get channels
        result, error = emby_api_request(url, token, 'GET', '/LiveTv/Channels')

        if not result:
            return jsonify({'error': error or 'Failed to get channels'}), 500

        channels = result.get('Items', [])
        total_channels = len(channels)

        def generate():
            channels_processed = 0
            logo_types = ['Primary', 'LogoLight', 'LogoLightColor']

            for channel in channels:
                channel_id = channel.get('Id')
                channel_name = channel.get('Name', 'Unknown')

                if not channel_id:
                    continue

                channels_processed += 1

                # Send progress update
                yield f"data: {json.dumps({'progress': channels_processed, 'total': total_channels, 'channel': channel_name})}\n\n"

                for logo_type in logo_types:
                    emby_api_request(url, token, 'DELETE', f'/Items/{channel_id}/Images/{logo_type}')

            # Send completion
            yield f"data: {json.dumps({'done': True, 'channels_processed': channels_processed})}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        logger.error(f"Error deleting Emby logos: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/emby/clear-channel-numbers', methods=['POST'])
def clear_emby_channel_numbers():
    """Clear all channel numbers from Emby Live TV channels with SSE progress updates"""
    try:
        data = request.json
        url = data.get('url', '').rstrip('/')
        username = data.get('username')
        password = data.get('password')

        token, user_id = emby_authenticate(url, username, password)

        if not token or not user_id:
            return jsonify({'error': 'Authentication failed'}), 401

        # Get channels from management endpoint
        result, error = emby_api_request(url, token, 'GET', '/emby/LiveTv/Manage/Channels')

        if not result:
            return jsonify({'error': error or 'Failed to get channels'}), 500

        channels = result.get('Items', [])
        # Only count channels that have numbers
        channels_with_numbers = [ch for ch in channels if ch.get('ChannelNumber')]
        total_channels = len(channels_with_numbers)

        def generate():
            channels_cleared = 0
            channels_processed = 0

            for channel in channels_with_numbers:
                channel_id = channel.get('Id')
                channel_name = channel.get('Name', 'Unknown')

                if not channel_id:
                    continue

                channels_processed += 1

                # Send progress update
                yield f"data: {json.dumps({'progress': channels_processed, 'total': total_channels, 'channel': channel_name})}\n\n"

                # Get full channel data
                channel_data, error = emby_api_request(url, token, 'GET', f'/Users/{user_id}/Items/{channel_id}')

                if not channel_data:
                    continue

                # Clear channel number
                channel_data['Number'] = ''
                channel_data['ChannelNumber'] = ''

                # Update channel
                query_params = f"X-Emby-Client=Emby+Web&X-Emby-Device-Name=ChannelIdentifiarr&X-Emby-Device-Id=channelidentifiarr&X-Emby-Client-Version=0.3.2-alpha&X-Emby-Token={token}&X-Emby-Language=en-us&reqformat=json"
                update_result, error = emby_api_request(url, token, 'POST', f'/emby/Items/{channel_id}?{query_params}', channel_data)

                if update_result is not None:
                    channels_cleared += 1

            # Send completion
            yield f"data: {json.dumps({'done': True, 'channels_cleared': channels_cleared})}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        logger.error(f"Error clearing Emby channel numbers: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# SETTINGS API ENDPOINTS
# ============================================================================

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get all application settings (without sensitive values in logs)"""
    try:
        settings = settings_manager.load_settings()
        return jsonify(settings)
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def save_settings():
    """Save application settings"""
    try:
        new_settings = request.json

        if not new_settings:
            return jsonify({'error': 'No settings provided'}), 400

        success = settings_manager.save_settings(new_settings)

        if success:
            return jsonify({'success': True, 'message': 'Settings saved successfully'})
        else:
            return jsonify({'error': 'Failed to save settings'}), 500

    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['PATCH'])
def update_settings():
    """Update specific settings without overwriting all"""
    try:
        updates = request.json

        if not updates:
            return jsonify({'error': 'No updates provided'}), 400

        success = settings_manager.update_settings(updates)

        if success:
            return jsonify({'success': True, 'message': 'Settings updated successfully'})
        else:
            return jsonify({'error': 'Failed to update settings'}), 500

    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/test-dispatcharr', methods=['POST'])
def test_dispatcharr_settings():
    """Test Dispatcharr connection with provided or saved settings"""
    try:
        # Use provided settings or load from storage
        data = request.json or {}

        if data.get('url'):
            # Test with provided settings
            url = data.get('url')
            username = data.get('username')
            password = data.get('password')
        else:
            # Test with saved settings
            settings = settings_manager.load_settings()
            if not settings.get('dispatcharr'):
                return jsonify({'success': False, 'error': 'No Dispatcharr settings found'}), 400

            url = settings['dispatcharr'].get('url')
            username = settings['dispatcharr'].get('username')
            password = settings['dispatcharr'].get('password')

        if not all([url, username, password]):
            return jsonify({'success': False, 'error': 'Missing credentials'}), 400

        # Try to authenticate
        token = get_dispatcharr_token(url, username, password)
        if token:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Authentication failed'}), 401

    except Exception as e:
        logger.error(f"Connection test error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings/test-emby', methods=['POST'])
def test_emby_settings():
    """Test Emby connection with provided or saved settings"""
    try:
        # Use provided settings or load from storage
        data = request.json or {}

        if data.get('url'):
            # Test with provided settings
            url = data.get('url', '').rstrip('/')
            username = data.get('username')
            password = data.get('password')
        else:
            # Test with saved settings
            settings = settings_manager.load_settings()
            if not settings.get('emby'):
                return jsonify({'success': False, 'error': 'No Emby settings found'}), 400

            url = settings['emby'].get('url', '').rstrip('/')
            username = settings['emby'].get('username')
            password = settings['emby'].get('password')

        if not url:
            return jsonify({'success': False, 'error': 'URL required'}), 400

        # Try to authenticate
        token, user_id = emby_authenticate(url, username, password)

        if not token:
            return jsonify({'success': False, 'error': 'Authentication failed'}), 401

        # Get server info
        result, error = emby_api_request(url, token, 'GET', '/emby/System/Info')

        if result:
            return jsonify({
                'success': True,
                'server_name': result.get('ServerName', 'Emby Server'),
                'version': result.get('Version', 'Unknown')
            })
        else:
            return jsonify({'success': False, 'error': error or 'Connection failed'}), 500

    except Exception as e:
        logger.error(f"Emby connection test error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Check if database exists
    if not Path(DB_PATH).exists():
        logger.error(f"Database not found at {DB_PATH}")
        logger.info("Please mount the database or set DATABASE_PATH environment variable")
    else:
        logger.info(f"Using database at {DB_PATH}")

    # Run the development server
    app.run(host='0.0.0.0', port=5000, debug=False)