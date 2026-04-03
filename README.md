# 🍔 Bitenex API

Production-grade backend for the **Bitenex** food delivery platform — connecting users, merchants, and drivers. Handles the full order lifecycle, real-time dispatch, payments (VNPay), and notifications.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.124-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Redis 7](https://img.shields.io/badge/Redis-7-DC382D.svg)](https://redis.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Quick Start (Docker)](#quick-start-docker)
    - [Local Development (without Docker)](#local-development-without-docker)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Database & Migrations](#database--migrations)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Available Make Commands](#available-make-commands)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **User Management** — Registration, authentication, profile management with role-based access (User, Driver, Merchant, Admin)
- **Merchant Management** — Restaurant onboarding, menu management with item options, operational status control
- **Order Lifecycle** — Full order flow from creation through delivery with validated state transitions
- **Real-time Dispatch** — WebSocket-based driver dispatch with multiple strategies (nearest, least busy, round robin)
- **Payment Integration** — VNPay payment gateway with idempotency keys and webhook event handling
- **Notifications** — Multi-channel notifications (push, SMS, email, in-app)
- **Admin Panel** — Administrative endpoints for platform management and oversight
- **Soft Delete** — All records use soft deletion for data integrity and audit trails
- **JWT Authentication** — Access & refresh token flow with role-based authorization

---

## Tech Stack

| Category        | Technology                              |
| --------------- | --------------------------------------- |
| **Language**    | Python 3.11+                            |
| **Framework**   | FastAPI (async)                         |
| **ORM**         | SQLAlchemy 2.0 (async + asyncpg)        |
| **Database**    | PostgreSQL 16                           |
| **Cache/Queue** | Redis 7                                 |
| **Migrations**  | Alembic                                 |
| **Auth**        | JWT (PyJWT) + bcrypt (passlib)          |
| **Validation**  | Pydantic v2 + pydantic-settings         |
| **Testing**     | pytest + pytest-asyncio (SQLite in-mem) |
| **Linting**     | Ruff, Black, mypy (strict)              |
| **Containers**  | Docker + Docker Compose                 |
| **WebSocket**   | FastAPI WebSocket + websockets          |

---

## Architecture

```
app/
├── core/               # Framework configuration
│   ├── config.py       # Settings (pydantic-settings, .env)
│   ├── database.py     # Async engine & session factory
│   ├── dependencies.py # Auth, role checks, DI helpers
│   ├── exceptions.py   # Custom exception hierarchy
│   └── security.py     # JWT & password utilities
├── modules/            # Domain modules (see below)
│   ├── auth/           # Authentication & registration
│   ├── user/           # User profiles
│   ├── merchant/       # Merchant & menu management
│   ├── driver/         # Driver management
│   ├── order/          # Order lifecycle
│   ├── dispatch/       # Driver dispatch logic
│   ├── payment/        # Payment processing (VNPay)
│   ├── notification/   # Multi-channel notifications
│   ├── admin/          # Admin operations
│   └── system/         # Health checks & system info
├── realtime/           # WebSocket manager
├── shared/             # Shared enums, DTOs, utilities
├── workers/            # Background workers
└── tests/              # Test suite
```

Each domain module follows a strict **4-file pattern**:

| File         | Responsibility                                        |
| ------------ | ----------------------------------------------------- |
| `models.py`  | SQLAlchemy ORM models (inherit `BaseModel`)           |
| `schemas.py` | Pydantic request/response DTOs (inherit `BaseDTO`)    |
| `service.py` | Business logic class, injected with `AsyncSession`    |
| `router.py`  | FastAPI endpoints, service via `Depends(get_service)` |

**Data Flow:**

```
Router (HTTP) → Service (business logic) → Model (ORM) → Database
       ↓              ↓
   Schemas       Exceptions
```

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/) (recommended)
- **OR** Python 3.11+, PostgreSQL 16, Redis 7 (for local development)

### Quick Start (Docker)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/bitenex-api.git
cd bitenex-api

# 2. Copy environment file
cp .env.example .env  # Edit as needed

# 3. Build and start all services
make build
make up

# 4. Run database migrations
make migrate

# 5. API is now running at http://localhost:8000
#    Swagger docs at http://localhost:8000/docs
```

### Local Development (without Docker)

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Edit .env with your local PostgreSQL and Redis URLs

# 4. Run migrations
alembic upgrade head

# 5. Start the development server
uvicorn app.main:app --reload --port 8000
```

---

## Configuration

Configuration is managed via environment variables using `pydantic-settings`. Create a `.env` file in the project root:

```env
# Application
APP_NAME=Bitenex
APP_ENV=dev                # dev | stg | prod
DEBUG=true
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/bitenex

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]

# VNPay
VNP_TMN_CODE=your-terminal-code
VNP_HASH_SECRET=your-hash-secret
VNP_URL=https://sandbox.vnpayment.vn/paymentv2/vpcpay.html
VNP_RETURN_URL=http://localhost:3000/payment/return
VNP_IPN_URL=http://localhost:8000/api/v1/payments/vnpay/ipn
```

---

## API Documentation

When running in development mode (`DEBUG=true`), interactive API docs are available at:

| Tool        | URL                                |
| ----------- | ---------------------------------- |
| **Swagger** | http://localhost:8000/docs         |
| **ReDoc**   | http://localhost:8000/redoc        |
| **OpenAPI** | http://localhost:8000/openapi.json |
| **Health**  | http://localhost:8000/health       |

### API Endpoints Overview

All domain endpoints are prefixed with `/api/v1`:

| Module        | Prefix                  | Description                     |
| ------------- | ----------------------- | ------------------------------- |
| Auth          | `/api/v1/auth`          | Login, register, refresh tokens |
| Users         | `/api/v1/users`         | User profile management         |
| Merchants     | `/api/v1/merchants`     | Merchant & menu operations      |
| Drivers       | `/api/v1/drivers`       | Driver management & status      |
| Orders        | `/api/v1/orders`        | Order CRUD & lifecycle          |
| Dispatch      | `/api/v1/dispatch`      | Driver dispatch & assignment    |
| Payments      | `/api/v1/payments`      | Payment processing & webhooks   |
| Notifications | `/api/v1/notifications` | Notification management         |
| Admin         | `/api/v1/admin`         | Admin operations                |

---

## Database & Migrations

The project uses **Alembic** for database migrations with an async PostgreSQL driver (`asyncpg`).

```bash
# Run all pending migrations
make migrate

# Create a new migration (auto-generates from model changes)
make migrate-new

# Rollback one migration
make migrate-down

# Check current revision
docker compose exec api alembic current

# View migration history
docker compose exec api alembic history
```

### Key Conventions

- **Primary keys**: UUID strings (`String(36)`, auto-generated)
- **Timestamps**: All models include `created_at`, `updated_at` via `BaseModel`
- **Soft delete**: Models have `is_deleted` and `deleted_at` fields — use `model.soft_delete()`, never hard delete
- **Naming**: Enforced convention (e.g., `fk_tablename_column_referred`)

---

## Testing

Tests use **pytest** with async support and an in-memory SQLite database.

```bash
# Run all tests (Docker)
make test

# Run with coverage report
make test-cov

# Run locally
pytest -v

# Run a specific test file
pytest app/tests/test_auth.py -v

# Run a specific test
pytest app/tests/test_auth.py::test_login -v
```

### Test Structure

```
app/tests/
├── conftest.py                             # Shared fixtures (db_session, client)
├── test_api.py                             # General API tests
├── test_auth.py                            # Authentication tests
├── test_merchant_api.py                    # Merchant endpoint tests
├── test_merchant_service.py                # Merchant service unit tests
├── test_order_transactional.py             # Order transaction tests
├── test_payment_vnpay_idempotency.py       # Payment idempotency tests
└── test_admin_order_payment_management.py  # Admin management tests
```

---

## Project Structure

```
bitenex-api/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── core/                # Framework & infrastructure
│   │   ├── config.py        # Settings management
│   │   ├── database.py      # Database engine & sessions
│   │   ├── dependencies.py  # Dependency injection (auth, roles)
│   │   ├── events.py        # Application events
│   │   ├── exceptions.py    # Custom exception hierarchy
│   │   ├── exception_handlers.py
│   │   └── security.py      # JWT & password hashing
│   ├── modules/             # Domain modules
│   │   ├── base.py          # BaseModel (UUID, timestamps, soft-delete)
│   │   ├── auth/            # Authentication & registration
│   │   ├── user/            # User profiles
│   │   ├── merchant/        # Merchants & menus
│   │   ├── driver/          # Driver management
│   │   ├── order/           # Order lifecycle
│   │   ├── dispatch/        # Dispatch strategies
│   │   ├── payment/         # Payment processing
│   │   ├── notification/    # Notifications
│   │   ├── admin/           # Admin operations
│   │   └── system/          # Health & system info
│   ├── realtime/            # WebSocket connection manager
│   ├── shared/              # Shared utilities
│   │   ├── dto.py           # Base DTOs & pagination
│   │   ├── enums.py         # Status & type enums
│   │   └── utils.py         # Helper functions
│   ├── workers/             # Background workers
│   └── tests/               # Test suite
├── alembic/                 # Database migrations
├── scripts/                 # Database init scripts
├── docker-compose.yml       # Development services
├── docker-compose.prod.yml  # Production services
├── Dockerfile               # Multi-stage Docker build
├── Makefile                 # Developer commands
├── requirements.txt         # Python dependencies
└── pyproject.toml           # Project & tool configuration
```

---

## Available Make Commands

| Command             | Description                                |
| ------------------- | ------------------------------------------ |
| `make help`         | Show all available commands                |
| `make build`        | Build Docker images                        |
| `make up`           | Start all services (API, DB, Redis)        |
| `make down`         | Stop all services                          |
| `make restart`      | Restart all services                       |
| `make logs`         | View logs (all services)                   |
| `make logs-api`     | View API logs only                         |
| `make shell`        | Open shell in API container                |
| `make db-shell`     | Open PostgreSQL shell                      |
| `make migrate`      | Run Alembic migrations                     |
| `make migrate-new`  | Create a new migration                     |
| `make migrate-down` | Rollback one migration                     |
| `make test`         | Run tests                                  |
| `make test-cov`     | Run tests with coverage report             |
| `make lint`         | Run Ruff linting                           |
| `make format`       | Format code (Black + Ruff fix)             |
| `make dev-tools`    | Start with pgAdmin (http://localhost:5050) |
| `make prod-up`      | Start production services                  |
| `make prod-down`    | Stop production services                   |
| `make clean`        | Remove containers and volumes              |
| `make prune`        | Remove all unused Docker resources         |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow the module pattern (models → schemas → service → router)
4. Write tests for new functionality
5. Ensure linting passes (`make lint`)
6. Commit your changes (`git commit -m 'feat: add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Code Style

- **Line length**: 100 characters (Ruff + Black)
- **Type hints**: Required on all functions (mypy strict mode)
- **Imports**: Absolute imports from `app.` namespace
- **Exceptions**: Always use `BitenexException` subclasses
- **Deletion**: Soft delete only — never hard delete records

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
