# Crypto Signal Aggregator & Analysis API

A high-performance FastAPI-based cryptocurrency signal aggregation system that monitors Telegram channels for token announcements, performs analytics on historical data, and provides both REST API and responsive web interface.

## Features

- **Telegram Integration**: Monitor multiple channels for crypto trading signals (with mock mode for development)
- **Real-time Updates**: WebSocket support for live signal streaming
- **High-Performance Caching**: Redis-backed caching with 100-200x performance improvement
- **100,000+ Record Support**: Designed to handle large datasets efficiently
- **Responsive Web UI**: Mobile-first design with Tailwind CSS and Chart.js
- **Comprehensive Analytics**: Token stats, channel leaderboards, market patterns
- **Load Testing**: Locust tests for 10/100/1000 concurrent users

## Quick Start

### Using Docker (Recommended)

```bash
# Clone and navigate
cd crypto-signal-aggregator

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Access the app
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
# Dashboard: http://localhost:8000/
```

### Manual Setup

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Unix

# Install dependencies
pip install -r requirements.txt

# Set up environment
copy .env.example .env
# Edit .env with your settings

# Start Redis (required for caching)
docker run -d -p 6379:6379 redis:7-alpine

# Run the application
uvicorn app.main:app --reload

# Generate test data (optional)
# The app auto-generates 100k+ records on startup
```

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                        Client Layer                            │
├────────────────────────────────────────────────────────────────┤
│  Web Browser  │  Mobile App  │  API Clients  │  WebSocket     │
└───────┬───────┴──────┬───────┴───────┬───────┴───────┬────────┘
        │              │               │               │
        ▼              ▼               ▼               ▼
┌────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                         │
├────────────────────────────────────────────────────────────────┤
│  REST API  │  WebSocket  │  Jinja2 Templates  │  Static Files │
├────────────────────────────────────────────────────────────────┤
│                    Service Layer                               │
├────────────────────────────────────────────────────────────────┤
│  SignalParser  │  Analytics  │  TelegramMonitor  │  DataGen   │
└───────┬────────┴──────┬──────┴────────┬──────────┴─────┬──────┘
        │               │               │                │
        ▼               ▼               ▼                ▼
┌───────────────┐ ┌─────────────┐ ┌───────────────┐ ┌───────────┐
│  PostgreSQL   │ │   Redis     │ │   Telegram    │ │   Faker   │
│  (Database)   │ │   (Cache)   │ │    (API)      │ │  (Mock)   │
└───────────────┘ └─────────────┘ └───────────────┘ └───────────┘
```

## API Endpoints

### Signals

| Method | Endpoint               | Description                            |
| ------ | ---------------------- | -------------------------------------- |
| GET    | `/api/v1/signals`      | List signals with pagination & filters |
| GET    | `/api/v1/signals/{id}` | Get signal by ID                       |
| POST   | `/api/v1/signals`      | Create new signal                      |
| DELETE | `/api/v1/signals/{id}` | Delete signal                          |

### Analytics (Cached)

| Method | Endpoint                                 | Cache TTL | Description                  |
| ------ | ---------------------------------------- | --------- | ---------------------------- |
| GET    | `/api/v1/analytics/historical`           | 5 min     | Historical data with summary |
| GET    | `/api/v1/analytics/token/{symbol}/stats` | 1 min     | Token-specific statistics    |
| GET    | `/api/v1/analytics/channels/leaderboard` | 1 hour    | Channel performance rankings |
| GET    | `/api/v1/analytics/patterns`             | 10 min    | Detected market patterns     |
| GET    | `/api/v1/analytics/benchmark`            | -         | Run cache benchmark          |

### Channels

| Method | Endpoint                | Description         |
| ------ | ----------------------- | ------------------- |
| GET    | `/api/v1/channels`      | List all channels   |
| GET    | `/api/v1/channels/{id}` | Get channel details |
| POST   | `/api/v1/channels`      | Create channel      |

### WebSocket

| Endpoint          | Description             |
| ----------------- | ----------------------- |
| `/api/v1/live/ws` | Real-time signal stream |

## Cache Performance

The system demonstrates significant performance improvements with Redis caching:

| Metric            | Without Cache | With Cache | Improvement       |
| ----------------- | ------------- | ---------- | ----------------- |
| Response Time     | 1,500-3,000ms | 10-20ms    | **100-200x**      |
| Records Processed | 100,000+      | From cache | -                 |
| Database Load     | High          | Minimal    | **95% reduction** |

See [PERFORMANCE.md](PERFORMANCE.md) for detailed benchmarks.

## Web Interface

The responsive web interface includes:

- **Dashboard**: Real-time stats, signal feed, trending tokens
- **Signals**: Searchable list with filters and pagination
- **Analytics**: Charts, leaderboards, pattern detection

Features:

- Mobile-first responsive design
- Dark mode support
- Real-time updates via WebSocket
- Touch-friendly controls

## Testing

### Unit & Integration Tests

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_unit.py -v
```

### Load Testing

```bash
# Light load (10 users)
locust -f tests/locust_load_test.py --host=http://localhost:8000 --users=10 --spawn-rate=2

# Medium load (100 users)
locust -f tests/locust_load_test.py --host=http://localhost:8000 --users=100 --spawn-rate=10

# Heavy load (1000 users)
locust -f tests/locust_load_test.py --host=http://localhost:8000 --users=1000 --spawn-rate=50

# Web UI mode
locust -f tests/locust_load_test.py --host=http://localhost:8000
# Open http://localhost:8089
```

## Configuration

### Environment Variables

| Variable             | Description                  | Default                    |
| -------------------- | ---------------------------- | -------------------------- |
| `DATABASE_URL`       | PostgreSQL connection string | SQLite (dev)               |
| `REDIS_URL`          | Redis connection string      | `redis://localhost:6379/0` |
| `SECRET_KEY`         | Application secret key       | Required                   |
| `TELEGRAM_API_ID`    | Telegram API ID              | Optional                   |
| `TELEGRAM_API_HASH`  | Telegram API hash            | Optional                   |
| `TELEGRAM_MOCK_MODE` | Use mock Telegram client     | `true`                     |
| `LOG_LEVEL`          | Logging level                | `INFO`                     |
| `CORS_ORIGINS`       | Allowed CORS origins         | `["*"]`                    |

### Cache TTL Configuration

Adjust cache TTL values in `app/routers/analytics.py`:

```python
@cache(expire=300)  # 5 minutes for historical data
@cache(expire=60)   # 1 minute for token stats
@cache(expire=3600) # 1 hour for leaderboard
@cache(expire=600)  # 10 minutes for patterns
```

## Project Structure

```
crypto-signal-aggregator/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings management
│   ├── database.py          # Database setup
│   ├── cache.py             # Redis cache setup
│   ├── models/              # SQLAlchemy models
│   │   ├── signal.py
│   │   ├── channel.py
│   │   └── token.py
│   ├── schemas/             # Pydantic schemas
│   │   ├── signal.py
│   │   ├── channel.py
│   │   └── analytics.py
│   ├── routers/             # API endpoints
│   │   ├── signals.py
│   │   ├── analytics.py
│   │   ├── channels.py
│   │   └── live.py
│   ├── services/            # Business logic
│   │   ├── synthetic_data.py
│   │   ├── analytics_service.py
│   │   ├── signal_parser.py
│   │   └── telegram_monitor.py
│   └── utils/               # Utilities
│       ├── helpers.py
│       └── validators.py
├── templates/               # Jinja2 templates
│   ├── base.html
│   ├── index.html
│   ├── signals.html
│   └── analytics.html
├── static/                  # Static assets
│   ├── css/custom.css
│   └── js/app.js
├── tests/                   # Test suite
│   ├── test_unit.py
│   ├── test_integration.py
│   ├── test_cache.py
│   └── locust_load_test.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Development

### Adding New Endpoints

1. Create/update schema in `app/schemas/`
2. Add router in `app/routers/`
3. Include router in `app/main.py`
4. Add tests in `tests/`

### Adding Cache to Endpoints

```python
from fastapi_cache.decorator import cache

@router.get("/expensive-query")
@cache(expire=300)  # Cache for 5 minutes
async def expensive_query():
    # Heavy computation here
    return result
```

## Deployment

### Production with Docker Compose

```bash
# Build and run production
docker-compose -f docker-compose.prod.yml up -d

# Scale application
docker-compose -f docker-compose.prod.yml up -d --scale app=3
```

### Environment Setup

1. Copy `.env.example` to `.env`
2. Set strong `SECRET_KEY`
3. Configure `POSTGRES_PASSWORD`
4. Set `TELEGRAM_*` credentials for live monitoring
5. Configure `CORS_ORIGINS` for your domain

## License

MIT License

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push branch (`git push origin feature/amazing`)
5. Open Pull Request
