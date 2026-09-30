"""Database connection and session handling using SQLAlchemy."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

# SQLite needs connect_args check_same_thread=False
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency that yields an isolated DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize all tables defined in models and ensure new columns exist."""
    from sqlalchemy import text
    import backend.app.models.dataset  # ensure models are loaded
    import backend.app.models.user
    import backend.app.models.job
    Base.metadata.create_all(bind=engine)
    
    with engine.connect() as conn:
        try:
            res = conn.execute(text("PRAGMA table_info(analysis_jobs)")).fetchall()
            existing_cols = {row[1] for row in res}
            if existing_cols:
                if "current_step" not in existing_cols:
                    conn.execute(text("ALTER TABLE analysis_jobs ADD COLUMN current_step INTEGER DEFAULT 0"))
                if "phase" not in existing_cols:
                    conn.execute(text("ALTER TABLE analysis_jobs ADD COLUMN phase VARCHAR DEFAULT 'queued'"))
                conn.commit()
        except Exception:
            pass
