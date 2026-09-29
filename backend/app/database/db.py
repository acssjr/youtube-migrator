from sqlmodel import SQLModel, create_engine, Session
from app.config.config import settings

# Create engine with connect_args for SQLite to avoid thread conflicts
database_url = settings.DATABASE_URL
if database_url.startswith("postgres://"):
    database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
elif database_url.startswith("postgresql://"):
    database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
elif database_url.startswith("sqlite:///") and not database_url.startswith("sqlite:////"):
    database_url = f"sqlite:///{settings.db_path}"
engine = create_engine(database_url, echo=settings.DEBUG,
                       connect_args={"check_same_thread": False} if database_url.startswith("sqlite:") else {},
                       pool_pre_ping=True)

def init_db():
    """Create database tables if they do not exist."""
    if not settings.VERCEL:
        settings.ensure_directories()
    SQLModel.metadata.create_all(engine)
    if settings.VERCEL:
        return
    
    # Simple migration: add target_playlist_id column to migration_tasks if missing
    from sqlalchemy import text
    with Session(engine) as session:
        try:
            session.exec(text("SELECT target_playlist_id FROM migration_tasks LIMIT 1"))
        except Exception:
            try:
                session.exec(text("ALTER TABLE migration_tasks ADD COLUMN target_playlist_id VARCHAR"))
                session.commit()
            except Exception as e:
                from loguru import logger
                logger.error(f"Migration error (adding target_playlist_id): {e}")

def get_session():
    """Dependency generator for database sessions."""
    with Session(engine) as session:
        yield session
