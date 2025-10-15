# ChannelIdentifiarr

**v0.5.0**

Web-based TV channel lineup search and Dispatcherr/Emby integration.

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
