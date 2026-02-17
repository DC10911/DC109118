# BOT-FORGE

**Meta-bot factory that generates production-ready bots from JSON specifications.**

BOT-FORGE takes a simple JSON spec describing what bot you want, and produces a complete, tested, deployable project — including code, tests, Docker configuration, CI pipeline, and documentation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          BOT-FORGE                                  │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │  INTAKE   │→│   PLAN    │→│  RETRIEVE  │→│     GENERATE     │  │
│  │ (validate │  │ (files,  │  │  (docs &   │  │ (Jinja2 render │  │
│  │  spec)    │  │  deps)   │  │  context)  │  │  from templates)│  │
│  └──────────┘  └──────────┘  └───────────┘  └──────────────────┘  │
│       │                                              │              │
│       │         ┌──────────┐  ┌───────────┐  ┌──────┴───────────┐  │
│       │         │  DEPLOY   │←│  PACKAGE   │←│      TEST        │  │
│       │         │ (output   │  │ (tar.gz   │  │ (compile check  │  │
│       │         │  to disk) │  │  archive)  │  │  + pytest)      │  │
│       │         └──────────┘  └───────────┘  └──────────────────┘  │
│       │                                              │              │
│       │                                       ┌──────┴───────────┐  │
│       │                                       │     REVIEW       │  │
│       │                                       │ (security scan   │  │
│       └──────── SQLite DB (job tracking) ─────│  + structure)    │  │
│                                               └──────────────────┘  │
│                                                                     │
│  Interfaces:  CLI (click + rich)  │  REST API (FastAPI)             │
└─────────────────────────────────────────────────────────────────────┘
```

## Modules

| Module | Description |
|--------|-------------|
| `core/config.py` | Settings loaded from environment variables |
| `core/models.py` | Pydantic models: BotSpec, JobRecord, pipeline stages |
| `core/database.py` | Async SQLite repository (swappable to Postgres) |
| `core/pipeline.py` | Pipeline orchestrator: Intake → Deploy |
| `agents/planner.py` | Converts spec → project plan (file list, deps) |
| `agents/retriever.py` | Adds platform best-practice context |
| `agents/generator.py` | Jinja2 template renderer |
| `agents/tester.py` | Runs compile checks + pytest on generated code |
| `agents/reviewer.py` | Static analysis + security scan |
| `agents/packager.py` | Creates tar.gz archive |
| `ui/cli.py` | CLI interface (click + rich) |
| `ui/api.py` | REST API (FastAPI) |
| `templates/` | Jinja2 templates per platform |

## Supported Platforms

- **telegram** — python-telegram-bot
- **discord** — discord.py
- **slack** — slack-bolt
- **cli** — click
- **web-api** — FastAPI
- **custom** — generic scaffolding

## Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
cd bot-forge

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"
```

### Generate a Bot (CLI)

```bash
# Generate a Telegram echo bot
bot-forge forge examples/telegram-echo-bot.json

# Generate a CLI echo bot
bot-forge forge examples/cli-echo-bot.json

# List all jobs
bot-forge jobs

# Check job status
bot-forge status <job-id>

# List supported platforms
bot-forge platforms
```

### Generate a Bot (API)

```bash
# Start the API server
uvicorn ui.api:app --host 0.0.0.0 --port 8000

# POST a spec
curl -X POST http://localhost:8000/forge \
  -H "Content-Type: application/json" \
  -d @examples/telegram-echo-bot.json

# List jobs
curl http://localhost:8000/jobs
```

### Docker

```bash
# Build
docker build -t bot-forge .

# Run CLI
docker run -v $(pwd)/output:/app/output bot-forge forge examples/cli-echo-bot.json

# Run API server
docker-compose up bot-forge-api
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v
```

## Example: Generate a Telegram Echo Bot

1. Create a spec file (or use `examples/telegram-echo-bot.json`):

```json
{
  "name": "my-telegram-echo-bot",
  "platform": "telegram",
  "description": "A simple Telegram bot that echoes messages",
  "features": ["echo"],
  "env_vars": [
    {
      "name": "TELEGRAM_BOT_TOKEN",
      "description": "Token from @BotFather",
      "required": true
    }
  ],
  "include_docker": true,
  "include_ci": true,
  "include_tests": true
}
```

2. Run BOT-FORGE:

```bash
bot-forge forge examples/telegram-echo-bot.json
```

3. Output will be in `output/my-telegram-echo-bot/` with:
   - `main.py` — Bot entry point
   - `bot/handler.py` — Message handlers
   - `tests/test_handler.py` — Unit tests
   - `Dockerfile` + `docker-compose.yml`
   - `.github/workflows/ci.yml`
   - `README.md` with run instructions

## Bot Spec Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | yes | — | Bot name (auto-slugified) |
| `platform` | enum | yes | — | telegram/discord/slack/cli/web-api/custom |
| `description` | string | yes | — | What the bot does |
| `features` | string[] | no | ["echo"] | Bot capabilities |
| `env_vars` | object[] | no | [] | Environment variables |
| `dependencies` | string[] | no | [] | Additional pip packages |
| `include_docker` | bool | no | true | Generate Docker files |
| `include_ci` | bool | no | true | Generate GitHub Actions CI |
| `include_tests` | bool | no | true | Generate test files |
| `logging_level` | enum | no | INFO | DEBUG/INFO/WARNING/ERROR |

## License

MIT
