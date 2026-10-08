# SID//OS — Backend Engine

> Private personal assistant backend powered by FastAPI, SQLAlchemy 2.x, Alembic, and PostgreSQL.

---

## 1. Project Overview

**SID//OS** is a private personal assistant application designed with a high-performance, modular backend architecture following clean layer separation:

```text
Router  ──►  Service  ──►  Repository  ──►  Database (Async SQLAlchemy 2.x / PostgreSQL)
```

**Phase 0** establishes the backend foundation:
- FastAPI async application initialization with lifespan management
- Centralized configuration via `pydantic-settings`
- Async database connection pool and declarative base
- Alembic database migration environment for async SQLAlchemy
- Centralized routing, structured logging, baseline security headers, and consistent error handling
- Health checks for application (`/api/health`) and database connectivity (`/api/health/db`)
- Containerization with Docker & Docker Compose
- Testing foundation with `pytest` and `httpx`

---

## 2. Technology Stack

- **Runtime**: Python 3.13+
- **API Framework**: FastAPI
- **ASGI Server**: Uvicorn
- **Validation & Settings**: Pydantic v2 & Pydantic Settings
- **ORM & Database Toolkit**: SQLAlchemy 2.x (asyncio)
- **Async Driver**: asyncpg
- **Database**: PostgreSQL 16
- **Database Migrations**: Alembic
- **Testing**: pytest, pytest-asyncio, httpx
- **Code Quality**: Ruff (Linter & Formatter)
- **Containerization**: Docker & Docker Compose

---

## 3. Requirements

Ensure the following tools are installed on your system:

- **Python 3.13+**
- **Docker** & **Docker Compose**
- **Git**

---

## 4. Local Setup

### 4.1. Clone and Configure Environment

```bash
cd Sidverse-Engine

# Copy sample environment configuration
cp .env.example .env
```

### 4.2. Local Python Environment (Without Docker)

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate

# Install dependencies (including development tools)
pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 4.3. Run Application with Docker Compose (Recommended)

Start the PostgreSQL database and FastAPI backend:

```bash
docker compose up --build
```

To run in detached mode:

```bash
docker compose up -d
```

To shut down containers and networks:

```bash
docker compose down
```

### 4.4. Run Application Locally with Uvicorn

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 5. API Documentation & Endpoints

Once the application is running, access the interactive API docs:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

### Available Endpoints (Phase 0)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Application health check (`{"status": "ok"}`) |
| `GET` | `/api/health/db` | Database connectivity health check (`{"status": "ok", "database": "connected"}`) |

---

## 6. Database Migrations

Database migrations are managed using Alembic:

```bash
# Apply all migrations to the latest version
alembic upgrade head

# Roll back the most recent migration
alembic downgrade -1

# Create a new migration revision (in future phases)
alembic revision --autogenerate -m "create_initial_tables"
```

---

## 7. Testing & Code Quality

### 7.1. Run Test Suite

```bash
pytest
```

### 7.2. Linting and Formatting with Ruff

```bash
# Check code style and linting issues
ruff check .

# Check formatting
ruff format --check .

# Automatically apply formatting
ruff format .
```

---

## 8. Project Structure

```text
Sidverse-Engine/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application factory & middleware
│   ├── api/                        # API routes
│   │   ├── __init__.py
│   │   ├── router.py               # Central API router (/api)
│   │   └── health.py               # Health & Database check endpoints
│   ├── core/                       # Core system components
│   │   ├── __init__.py
│   │   ├── config.py               # Pydantic Settings & environment validation
│   │   ├── database.py             # Async SQLAlchemy engine, sessionmaker & get_db
│   │   ├── exceptions.py           # Custom exceptions & standardized handlers
│   │   └── logging.py              # Structured logging configuration
│   ├── dependencies/               # Reusable FastAPI dependency injections
│   │   └── __init__.py
│   ├── models/                     # SQLAlchemy declarative models
│   │   └── __init__.py
│   ├── repositories/               # Data access layer
│   │   └── __init__.py
│   ├── schemas/                    # Pydantic request & response schemas
│   │   └── __init__.py
│   └── services/                   # Business logic layer
│       └── __init__.py
├── migrations/                     # Alembic async migration environment
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── tests/                          # Automated test suite
│   ├── __init__.py
│   ├── conftest.py
│   └── test_health.py
├── .env.example                    # Safe development environment template
├── .gitignore                      # Git ignore configuration
├── alembic.ini                     # Alembic configuration
├── Dockerfile                      # Production-ready backend Dockerfile
├── docker-compose.yml              # Multi-container orchestration (FastAPI + PostgreSQL)
├── pyproject.toml                  # Project metadata & tool configuration
├── requirements.txt                # Production dependencies
├── requirements-dev.txt            # Development & testing dependencies
└── README.md
```