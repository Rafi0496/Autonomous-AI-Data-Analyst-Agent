"""Pytest fixtures and configuration."""
import os
import sys
import tempfile
import uuid
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Create a temporary SQLite database file for the test session
# Set DATABASE_URL and settings BEFORE importing app or database modules
_temp_db_name = f"test_analyst_{uuid.uuid4().hex}.db"
_temp_db_path = Path(tempfile.gettempdir()) / _temp_db_name
TEST_DATABASE_URL = f"sqlite:///{_temp_db_path.as_posix()}"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Ensure required directories exist for clean runs
(BASE_DIR / "data" / "uploads").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data" / "processed").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data" / "reports").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data" / "samples").mkdir(parents=True, exist_ok=True)

# Override settings.DATABASE_URL explicitly before app/database imports
from backend.app.core.config import settings
settings.DATABASE_URL = TEST_DATABASE_URL
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
settings.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import Base, engine, SessionLocal, init_db, get_db
from backend.app.main import app

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables in the temporary test database at session start, and clean up at teardown."""
    init_db()
    yield
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass
    try:
        engine.dispose()
    except Exception:
        pass
    if _temp_db_path.exists():
        try:
            _temp_db_path.unlink()
        except Exception:
            pass

@pytest.fixture
def db_session():
    """Yield an isolated database session per test with automatic rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def sample_datasets_dir():
    d1 = BASE_DIR / "data" / "samples"
    if (d1 / "retail_sales_messy.csv").exists():
        return d1
    return BASE_DIR / "backend" / "tests" / "test_datasets"
