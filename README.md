# Cortex

AI-powered knowledge assistant that answers questions using your Confluence documentation.

**Made with by [Mert Golcu](https://github.com/mgolcu00)**

## Features

- **Semantic Search**: Vector-based search using OpenAI embeddings and pgvector
- **AI-Powered Answers**: Intelligent responses with GPT-4/GPT-5 and source citations
- **Real-Time Sync**: Automatic synchronization with Confluence Cloud
- **Modern UI**: ChatGPT-like interface with dark theme (React + Vite)
- **Session Management**: PostgreSQL-backed persistent chat history
- **Usage Analytics**: Token usage, cost tracking, and API statistics
- **Customizable**: Editable agent instructions and conversation starters

## Quick Start

### Prerequisites

- Docker and Docker Compose (recommended)
- Or: Python 3.11+, Node.js 18+, PostgreSQL 15+ with pgvector

### 1. Clone and Configure

```bash
git clone https://github.com/mgolcu00/cortex.git
cd cortex

# Copy environment template
cp .env.example .env
```

Edit `.env` and fill in the required values:

```env
# OpenAI (Required)
OPENAI_API_KEY=sk-your-api-key-here

# Confluence (Required)
CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net/wiki
CONFLUENCE_EMAIL=your-email@company.com
CONFLUENCE_API_TOKEN=your-confluence-api-token

# PostgreSQL (Defaults work, change if needed)
POSTGRES_USER=cortex
POSTGRES_PASSWORD=cortex123
POSTGRES_DB=cortex_db
```

### 2. Start with Docker

```bash
docker-compose up -d
```

Open http://localhost:8000 in your browser.

### 3. Initial Setup

1. Go to **Settings** page
2. Verify configuration (green checkmarks)
3. Click **Sync Baslat** to start indexing
4. Wait for sync to complete
5. Go to **Chat** and start asking questions

## Installation Options

### Docker (Recommended)

Docker handles all dependencies automatically.

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove all data
docker-compose down -v
```

### Local Development

#### Requirements

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ with pgvector extension

#### Database Setup

Install pgvector:

```bash
# macOS
brew install pgvector

# Ubuntu/Debian
sudo apt install postgresql-15-pgvector
```

Create database:

```bash
psql -U postgres -c "CREATE DATABASE cortex_db;"
psql -U postgres -d cortex_db -c "CREATE EXTENSION vector;"
```

Update `.env` for local development:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/cortex_db
```

#### Run the Application

```bash
./run.sh
```

This script:
1. Creates Python virtual environment
2. Installs Python dependencies
3. Builds frontend (first run)
4. Starts the application

Open http://localhost:8000 in your browser.

## Project Structure

```
cortex/
├── app/                      # Backend (FastAPI)
│   ├── main.py              # API endpoints
│   ├── config.py            # Environment variables
│   ├── agent.py             # OpenAI Agent + Session management
│   ├── db/
│   │   ├── database.py      # PostgreSQL connection
│   │   ├── models.py        # SQLAlchemy models
│   │   └── vector_store.py  # pgvector operations
│   ├── confluence/
│   │   └── client.py        # Confluence API client
│   └── ingest/
│       ├── sync.py          # Synchronization
│       ├── chunker.py       # Text chunking
│       └── embedder.py      # OpenAI embeddings
│
├── frontend/                 # Frontend (React + Vite)
│   ├── src/
│   │   ├── pages/           # Page components
│   │   ├── components/      # UI components
│   │   └── lib/             # API, store, utils
│   └── package.json
│
├── docker-compose.yml        # Docker services
├── Dockerfile               # Application image
├── run.sh                   # Development script
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
└── README.md
```

## API Reference

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Send message, get AI response |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sessions` | List all sessions |
| GET | `/sessions/{id}` | Get session details |
| DELETE | `/sessions/{id}` | Delete session |

### Database

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/db/pages` | List indexed pages |
| GET | `/api/db/pages/{id}` | Get page details |
| GET | `/api/db/spaces` | List Confluence spaces |

### Sync

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sync/run` | Start synchronization |
| GET | `/sync/status` | Get sync status |

### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config` | Get current configuration |
| GET | `/api/instructions` | Get agent instructions |
| PUT | `/api/instructions` | Update instructions |
| GET | `/api/starters` | Get conversation starters |
| PUT | `/api/starters` | Update starters |
| GET | `/api/stats` | Get usage statistics |

## Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `CONFLUENCE_BASE_URL` | Yes | - | Confluence URL (https://xxx.atlassian.net/wiki) |
| `CONFLUENCE_EMAIL` | Yes | - | Confluence email |
| `CONFLUENCE_API_TOKEN` | Yes | - | Confluence API token |
| `POSTGRES_USER` | No | cortex | PostgreSQL username |
| `POSTGRES_PASSWORD` | No | cortex123 | PostgreSQL password |
| `POSTGRES_DB` | No | cortex_db | PostgreSQL database name |
| `DATABASE_URL` | No* | - | PostgreSQL URL for local development |
| `CHAT_MODEL` | No | gpt-4o | Chat model |
| `EMBEDDING_MODEL` | No | text-embedding-3-small | Embedding model |
| `SYNC_INTERVAL_MINUTES` | No | 60 | Auto-sync interval (minutes) |
| `LOG_LEVEL` | No | INFO | Log level |

> *`DATABASE_URL` is auto-generated for Docker. Only needed for local development.

## Troubleshooting

### Docker Issues

**Build error:**
```bash
docker-compose build --no-cache
docker-compose up -d
```

**Port in use:**
```bash
# Change ports in docker-compose.yml:
# - "5433:5432"  # PostgreSQL
# - "8001:8000"  # Application
```

**Database connection error:**
```bash
docker-compose logs db
# Wait for "database system is ready to accept connections"
```

### Confluence Issues

**API 401 Error:**
1. Check your API token: https://id.atlassian.com/manage/api-tokens
2. Verify email matches your Atlassian account
3. Ensure `CONFLUENCE_BASE_URL` ends with `/wiki`

**Empty Search Results:**
1. Run full synchronization first
2. Ensure pages have text content
3. Check sync status in Settings page

### pgvector Issues (Local)

```bash
# macOS
brew install pgvector
psql cortex_db -c "CREATE EXTENSION vector;"

# Ubuntu/Debian
sudo apt install postgresql-15-pgvector
psql cortex_db -c "CREATE EXTENSION vector;"
```

## Getting Help

If you encounter any issues or have questions:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Search existing [GitHub Issues](https://github.com/mgolcu00/cortex/issues)
3. Open a new issue with:
   - Description of the problem
   - Steps to reproduce
   - Error messages (if any)
   - Your environment (OS, Docker version, etc.)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License

---

**Cortex v2.0** - Made with by [Mert Golcu](https://github.com/mgolcu00)
