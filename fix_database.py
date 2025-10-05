#!/usr/bin/env python3
"""
Fix and optimize the database - add indexes for fast searching
"""

import sqlite3
import shutil
import time
from pathlib import Path

# The ORIGINAL compiled database
original_db = "/mnt/nvme/scratch/channelidentifiarr/channelidentifiarr.db"
plugin_db = "/mnt/docker/stacks/tv/config/dispatcharr/plugins/channelidentifiarr/channelidentifiarr.db"

print("=" * 60)
print("DATABASE RECOVERY AND OPTIMIZATION")
print("=" * 60)

# First, let's check both databases
print("\n1. Checking databases...")
print(f"Original DB size: {Path(original_db).stat().st_size / 1e9:.2f} GB")
print(f"Plugin DB size: {Path(plugin_db).stat().st_size / 1e9:.2f} GB")

# Test both databases
for db_path, name in [(original_db, "Original"), (plugin_db, "Plugin")]:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Test basic query
        cursor.execute("SELECT COUNT(*) FROM stations")
        station_count = cursor.fetchone()[0]

        # Test ESPN search
        cursor.execute("SELECT COUNT(*) FROM stations WHERE LOWER(name) LIKE '%espn%'")
        espn_count = cursor.fetchone()[0]

        print(f"\n{name} DB: {station_count} stations, {espn_count} ESPN matches")

        # Check for FTS table
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='stations_fts'")
        has_fts = cursor.fetchone()[0] > 0
        print(f"  Has FTS: {has_fts}")

        # Check for indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='stations'")
        indexes = [row[0] for row in cursor.fetchall()]
        print(f"  Station indexes: {len(indexes)}")

        conn.close()

    except Exception as e:
        print(f"\n{name} DB ERROR: {e}")

print("\n" + "=" * 60)
print("RECOVERY PLAN")
print("=" * 60)

# Let's fix the original database
print("\n2. Fixing the ORIGINAL database (removing FTS)...")

try:
    conn = sqlite3.connect(original_db)
    cursor = conn.cursor()

    # Remove FTS if it exists
    cursor.execute("DROP TABLE IF EXISTS stations_fts")
    cursor.execute("DROP TRIGGER IF EXISTS stations_ai")
    cursor.execute("DROP TRIGGER IF EXISTS stations_ad")
    cursor.execute("DROP TRIGGER IF EXISTS stations_au")

    print("   ✓ Removed FTS tables/triggers")

    # Run integrity check
    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()[0]
    print(f"   ✓ Integrity check: {result}")

    conn.commit()
    conn.close()

except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n3. Adding performance indexes to ORIGINAL database...")

try:
    conn = sqlite3.connect(original_db)
    cursor = conn.cursor()

    indexes_to_create = [
        # Critical for search performance
        ("idx_stations_name_lower", "CREATE INDEX IF NOT EXISTS idx_stations_name_lower ON stations(LOWER(name))"),
        ("idx_stations_call_lower", "CREATE INDEX IF NOT EXISTS idx_stations_call_lower ON stations(LOWER(call_sign))"),
        ("idx_station_lineups_composite", "CREATE INDEX IF NOT EXISTS idx_station_lineups_composite ON station_lineups(station_id, lineup_id)"),
        ("idx_lineup_markets_composite", "CREATE INDEX IF NOT EXISTS idx_lineup_markets_composite ON lineup_markets(lineup_id, country)"),
    ]

    for idx_name, idx_sql in indexes_to_create:
        print(f"   Creating {idx_name}...")
        start = time.time()
        cursor.execute(idx_sql)
        elapsed = time.time() - start
        print(f"   ✓ Created in {elapsed:.2f}s")

    # Analyze to update query planner stats
    print("   Analyzing database...")
    cursor.execute("ANALYZE")
    print("   ✓ Analysis complete")

    conn.commit()
    conn.close()

    print("\n✅ ORIGINAL DATABASE RECOVERED AND OPTIMIZED!")

except Exception as e:
    print(f"\n✗ Optimization failed: {e}")

print("\n4. Testing search performance...")

try:
    conn = sqlite3.connect(original_db)
    cursor = conn.cursor()

    # Test search speed
    start = time.time()
    cursor.execute("""
        SELECT COUNT(*) FROM stations s
        LEFT JOIN station_lineups sl ON s.station_id = sl.station_id
        WHERE LOWER(s.name) LIKE '%espn%'
    """)
    result = cursor.fetchone()[0]
    elapsed = time.time() - start

    print(f"   ESPN search with JOIN: {result} results in {elapsed:.3f}s")

    conn.close()

except Exception as e:
    print(f"   Search test failed: {e}")

print("\n" + "=" * 60)
print("RECOMMENDATION:")
print("Update docker-compose.yml to use the ORIGINAL database:")
print("/mnt/nvme/scratch/channelidentifiarr/channelidentifiarr.db")
print("=" * 60)