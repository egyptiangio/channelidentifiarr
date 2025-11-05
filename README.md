# ChannelIdentifiarr

**v0.6.2**

Web-based TV channel lineup search and Dispatcherr/Emby integration.

## Recent Updates (v0.6.2)

**Bug Fix:**
- **Clone Lineup** - Fixed credentials loading from backend settings instead of localStorage.

## Previous Updates (v0.6.1)

**Bug Fix:**
- **Clone Lineup** - Fixed "Dispatcharr credentials required" error. The frontend now correctly includes Dispatcharr credentials from settings when importing a lineup.

## Previous Updates (v0.6.0)

**New Features:**
- **Clone Lineup** - Import entire real-world lineups (DirecTV, Dish, cable providers) from Gracenote database with pre-populated channel numbers, station IDs, call signs, and logos. Search by ZIP code across all supported countries.
- **Selective Emby Logo Deletion** - Choose which logo types to delete (Primary, LogoLight, LogoLightColor) instead of removing all logos at once.
- **Logo Map Caching** - Significantly improved performance when loading Dispatcharr channels by caching logo data, reducing load times from minutes to seconds on large logo libraries.

## Previous Updates (v0.5.8)

**New Feature:**
- **Intelligent Channel Insertion** - Added ability to insert a channel at an occupied channel number with automatic shifting of existing channels upward until a gap is reached. The system intelligently detects when a selected channel number is already in use and offers the option to shift existing channels, eliminating the need for manual renumbering.

## Previous Updates (v0.5.7)

**Fixed Bugs:**
1. **Syntax error** - `try:` → `try {` (breaking UI)
2. **Sequential matching bug** - Removed stale channel references from onclick handlers

## Previous Updates (v0.5.6)

- **Channel Name Parsing** - Added "." to separator list for better parsing of period-delimited channel names
- **Manual Search Fix** - Fixed bug where sequential manual searches may only update the original channel

## Previous Updates (v0.5.5)

- **Logo Performance Fix** - Fixed slow channel creation when large logo databases were present by implementing smart collision resolution

## Previous Updates (v0.5.4)

- **Logo Deduplication Fix** - Fixed channel creation failures when using logos that already exist in Dispatcharr. The system now searches for existing logos by URL before attempting to create new ones, preventing duplicate logo errors.
- **Enhanced Channel Filtering** - Added comprehensive filtering for the Dispatcharr Integration tab including channel number (with range support like "100-200"), name, call sign, Gracenote ID, group, and logo presence. Select All now only selects visible filtered channels.
- **TVG-ID Source Selection** - Added option to populate TVG-ID field from either Call Sign or Gracenote ID when matching channels.
- **Bulk Operations** - Added bulk delete and bulk group edit functions for selected channels with confirmation dialogs.

## Features

- Search TV channels across multiple countries and lineups
- Smart channel matching with country/resolution detection
- Create channels directly from search results
- Advanced stream management and assignment
- Drag-and-drop stream ordering
- Channel renumbering with range selection
- Remote database update system with automatic backups

## Channel Creation from Search Results

ChannelIdentifiarr allows you to create Dispatcharr channels directly from Gracenote search results:

1. **Search for a station** - Use the search interface to find TV channels by name, call sign, or lineup
2. **Apply or Create Channel** - Click on a search result to either:
   - **Apply to Existing Channel** - Update an existing Dispatcharr channel with the station's metadata
   - **Create New Channel** - Create a new channel with pre-populated information from the Gracenote database
3. **Configure Channel Details**:
   - Channel name and number
   - Group assignment (with custom group filtering)
   - Channel number selection methods:
     - First Available - Find the first gap in your channel numbers
     - Highest + 1 - Add to the end of your lineup
     - Range - Select from suggested ranges (1-1000, 1001-2000, etc.) with usage statistics
   - TVG-ID and call sign
   - Logo (automatically uploaded to Dispatcharr)
4. **Assign Streams** (Optional):
   - Search for streams using auto-search or manual search
   - Add multiple streams and reorder them using drag-and-drop
   - View confidence scores and quality indicators
   - Filter by M3U playlist source

## Stream Management

Advanced stream management features integrated with Dispatcharr:

- **Stream Search & Assignment** - Search across all your M3U playlists to find matching streams
- **Auto-Search** - Intelligent stream matching based on channel name with quality detection
- **Manual Search** - Find streams with custom search terms
- **Drag-and-Drop Ordering** - Visually reorder streams with priority indicators
- **Quality Matching** - Automatic detection and matching of HD/UHD/SD quality variants
- **M3U Playlist Filtering** - See which playlist each stream comes from
- **Confidence Scoring** - View match quality scores for each stream suggestion
- **Stream Preview** - See stream URLs and metadata before assigning

## Additional Features

- **Database Updates** - Check for and download updated databases from remote sources with automatic backups
- **Group Management** - Create, edit, and delete custom channel groups
- **Default Groups** - Set default group for new channels with prominent display in Settings
- **Smart Ranges** - Define channel number ranges with automatic group assignment

## Quick Start

### Prerequisites

**Database Required:** The Gracenote data used by this application is proprietary and not provided here.

- Try asking in the Dispatcharr Discord for help obtaining a database
- Or build your own using the included tools (see [db-builder](db-builder/))

### Docker Compose

1. Download the compose file:
```bash
wget https://raw.githubusercontent.com/egyptiangio/channelidentifiarr/main/docker-compose.yml
```

2. Create a `data` directory and place your `channelidentifiarr.db` file in it:
```bash
mkdir data
cp /path/to/channelidentifiarr.db data/
```

3. Start:
```bash
docker-compose up -d
```

4. Open: http://localhost:9192

The database path can be configured in the Settings tab (defaults to `/data/channelidentifiarr.db`).

## License

MIT License - see [LICENSE](LICENSE)

## Links

- [Issues](https://github.com/egyptiangio/channelidentifiarr/issues)
- [Database Builder](db-builder/)
