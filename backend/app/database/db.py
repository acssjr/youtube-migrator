from sqlmodel import SQLModel, create_engine, Session
from app.config.config import settings

# Create engine with connect_args for SQLite to avoid thread conflicts
connect_args = {"check_same_thread": False}
engine = create_engine(
    f"sqlite:///{settings.db_path}", 
    echo=settings.DEBUG, 
    connect_args=connect_args
)

def init_db():
    """Create database tables if they do not exist."""
    settings.ensure_directories()
    SQLModel.metadata.create_all(engine)
    
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
