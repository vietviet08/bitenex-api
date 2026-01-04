# Bitenex API - Copilot Instructions

## Project Overview
Food delivery platform backend built with **FastAPI + SQLAlchemy async + PostgreSQL + Redis**. Python 3.11+.

## Architecture

### Module Structure (`app/modules/`)
Each domain module follows a strict 4-file pattern:
- `models.py` - SQLAlchemy ORM models, inherit from `BaseModel` (UUID pk, timestamps, soft-delete)
- `schemas.py` - Pydantic DTOs, inherit from `BaseDTO` for consistent config
- `service.py` - Business logic class, injected with `AsyncSession` via `__init__(self, db)`
- `router.py` - FastAPI endpoints, creates service via `Depends(get_service)` pattern

**Key modules:** `auth`, `user`, `driver`, `merchant`, `order`, `dispatch`, `payment`, `notification`, `admin`

### Data Flow Pattern
```
Router (HTTP) → Service (business logic) → Model (ORM) → Database
       ↓              ↓
   Schemas       Exceptions
```

### Key Patterns

**Dependencies injection** (`app/core/dependencies.py`):
```python
CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
# Role-based access: Depends(require_role(Role.ADMIN, Role.MERCHANT))
```

**Custom exceptions** (`app/core/exceptions.py`):
- Always raise `BitenexException` subclasses (`AuthenticationError`, `NotFoundError`, `ValidationError`, etc.)
- Include `message`, `code`, and optional `details` dict

**Enums** (`app/shared/enums.py`): All status/type enums inherit from `str, Enum` for JSON serialization.

## Key Conventions

### Models
- Primary keys: UUID strings (`String(36)`, auto-generated)
- All models have `created_at`, `updated_at`, `is_deleted`, `deleted_at` via `BaseModel`
- Use `soft_delete()` method, never hard delete

### Schemas (DTOs)
- Inherit from `BaseDTO` (enables ORM mode, strips whitespace, uses enum values)
- Use mixins: `TimestampMixin` for response DTOs with timestamps
- Generic pagination: `PaginatedResponse[T]`, `PaginationParams`

### Services
- Constructor takes `db: AsyncSession`
- All methods are `async`
- Status transitions validated in service (see `_validate_status_transition` pattern in order service)

### Routers
- Use service factory: `async def get_service(db = Depends(get_db)) -> Service: return Service(db)`
- Group endpoints by role with section comments (`# === User Endpoints ===`)

## Developer Commands

```bash
# Development (Docker)
make up              # Start all services (api, db, redis)
make logs-api        # Follow API logs
make shell           # Shell into API container
make dev-tools       # Start with pgAdmin

# Database
make migrate         # Run migrations (alembic upgrade head)
make migrate-new     # Create new migration (prompts for message)
alembic current      # Check current revision (local)

# Testing
make test            # Run pytest in container
make test-cov        # With coverage report

# Local dev (without Docker)
uvicorn app.main:app --reload
```

## Database & Migrations
- Alembic for migrations, async PostgreSQL (`asyncpg`)
- Naming convention enforced in `app/core/database.py` (e.g., `fk_tablename_column_referred`)
- Test database uses SQLite in-memory (`sqlite+aiosqlite:///:memory:`)

## Real-time Communication
`app/realtime/socket_manager.py` - WebSocket manager with room-based broadcasting.
Pattern: `ConnectionManager.send_personal(user_id, message)` or `broadcast_to_room(room, message)`

## Configuration
Settings via `pydantic-settings` from `.env` file (`app/core/config.py`). Access via:
```python
from app.core.config import get_settings
settings = get_settings()  # cached singleton
```

## Important Files
- [app/modules/base.py](app/modules/base.py) - Base model with UUID, timestamps, soft-delete
- [app/shared/dto.py](app/shared/dto.py) - Base DTO and pagination helpers
- [app/core/dependencies.py](app/core/dependencies.py) - Auth and role checking
- [app/core/exceptions.py](app/core/exceptions.py) - Custom exception hierarchy
