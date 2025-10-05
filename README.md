# ChannelIdentifiarr

**v0.1.0-alpha**

Web-based TV channel lineup search and Emby integration.

## Features

- Search TV channels across multiple countries and lineups
- Smart channel matching with country/resolution detection

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

2. Edit `docker-compose.yml` and update the database path:
```yaml
volumes:
  - /path/to/channelidentifiarr.db:/data/channelidentifiarr.db:ro
```

3. Start:
```bash
docker-compose up -d
```

4. Open: http://localhost:9192

## License

MIT License - see [LICENSE](LICENSE)

## Links

- [Issues](https://github.com/egyptiangio/channelidentifiarr/issues)
- [Database Builder](db-builder/)
