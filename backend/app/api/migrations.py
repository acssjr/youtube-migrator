from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
import os
from pathlib import Path
from loguru import logger

from app.database.db import get_session
from app.models.models import MigrationTask
from app.repositories.task_repository import TaskRepository
from app.schemas.schemas import TaskCreateRequest, TaskResponse, QueueMigrationRequest
from app.models.models import OAuthToken
from sqlmodel import select
from app.services.youtube_service import YoutubeService
from app.services.queue_service import QueueService

router = APIRouter(prefix="/migrations", tags=["migrations"])

@router.post("/queue", response_model=List[TaskResponse])
def queue_migrations(
    payload: QueueMigrationRequest,
    session: Session = Depends(get_session)
):
    """Add migration tasks to the background processing queue, optionally creating a target playlist."""
    task_repo = TaskRepository(session)
    queued_tasks = []
    
    # 1. Handle Playlist Creation if requested
    target_playlist_id = None
    if payload.create_playlist and payload.playlist_name and payload.tasks:
        try:
            # Get target channel token data
            target_channel_id = payload.tasks[0].target_channel_id
            token_record = session.exec(
                select(OAuthToken).where(OAuthToken.channel_id == target_channel_id)
            ).first()
            
            if token_record:
                yt_service = YoutubeService(token_record.token_data)
                # Create the playlist on target channel
                target_playlist_id = yt_service.create_playlist(
                    title=payload.playlist_name,
                    description=payload.playlist_description or "",
                    privacy_status=payload.playlist_privacy or "private"
                )
                
                # Download and set custom playlist thumbnail if provided
                if target_playlist_id and payload.playlist_thumbnail_url:
                    try:
                        import urllib.request
                        from app.config.config import settings
                        
                        downloads_dir = Path(settings.downloads_path)
                        downloads_dir.mkdir(parents=True, exist_ok=True)
                        temp_thumb_path = downloads_dir / f"playlist_thumb_{target_playlist_id}.jpg"
                        
                        logger.info(f"Downloading playlist cover from {payload.playlist_thumbnail_url}")
                        urllib.request.urlretrieve(payload.playlist_thumbnail_url, str(temp_thumb_path))
                        
                        if temp_thumb_path.exists():
                            yt_service.set_playlist_thumbnail(target_playlist_id, str(temp_thumb_path))
                            os.remove(temp_thumb_path)
                    except Exception as thumb_err:
                        logger.warning(f"Failed to set playlist thumbnail: {thumb_err}")
                        
        except Exception as e:
            # Log playlist creation error but don't fail the whole queue operation
            logger.error(f"Failed to create playlist on target: {e}")
            target_playlist_id = None
            
    # 2. Add tasks to database
    for item in payload.tasks:
        # Convert tags to a string representation for storage
        tags_str = ",".join(item.tags) if item.tags else None
        
        task = MigrationTask(
            video_id=item.video_id,
            title=item.title,
            description=item.description,
            tags=tags_str,
            category_id=item.category_id,
            language=item.language,
            thumbnail_url=item.thumbnail_url,
            source_channel_id=item.source_channel_id,
            source_channel_title=item.source_channel_title,
            target_channel_id=item.target_channel_id,
            status="pending",
            progress=0.0,
            privacy_status=item.privacy_status,
            scheduled_at=item.scheduled_at,
            target_playlist_id=target_playlist_id
        )
        task_repo.save(task)
        queued_tasks.append(task)
        
    # Start the queue loop if it's not active
    QueueService.get_instance().start()
    
    return [
        TaskResponse(
            id=t.id, video_id=t.video_id, title=t.title, description=t.description,
            tags=t.tags, category_id=t.category_id, language=t.language, thumbnail_url=t.thumbnail_url,
            source_channel_id=t.source_channel_id, source_channel_title=t.source_channel_title,
            target_channel_id=t.target_channel_id, target_channel_title=t.target_channel_title,
            status=t.status, progress=t.progress, error_message=t.error_message,
            privacy_status=t.privacy_status, scheduled_at=t.scheduled_at, created_at=t.created_at,
            started_at=t.started_at, completed_at=t.completed_at
        ) for t in queued_tasks
    ]

@router.get("/tasks", response_model=List[TaskResponse])
def get_tasks(session: Session = Depends(get_session)):
    """List all migration tasks (history and active queue)."""
    task_repo = TaskRepository(session)
    tasks = task_repo.get_all()
    return [
        TaskResponse(
            id=t.id, video_id=t.video_id, title=t.title, description=t.description,
            tags=t.tags, category_id=t.category_id, language=t.language, thumbnail_url=t.thumbnail_url,
            source_channel_id=t.source_channel_id, source_channel_title=t.source_channel_title,
            target_channel_id=t.target_channel_id, target_channel_title=t.target_channel_title,
            status=t.status, progress=t.progress, error_message=t.error_message,
            privacy_status=t.privacy_status, scheduled_at=t.scheduled_at, created_at=t.created_at,
            started_at=t.started_at, completed_at=t.completed_at
        ) for t in tasks
    ]

@router.post("/tasks/{task_id}/retry", response_model=TaskResponse)
def retry_task(task_id: int, session: Session = Depends(get_session)):
    """Reset a task status to pending to retry the migration."""
    task_repo = TaskRepository(session)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    task.status = "pending"
    task.progress = 0.0
    task.error_message = None
    task.started_at = None
    task.completed_at = None
    task_repo.save(task)
    
    QueueService.get_instance().start()
    
    return TaskResponse(
        id=task.id, video_id=task.video_id, title=task.title, description=task.description,
        tags=task.tags, category_id=task.category_id, language=task.language, thumbnail_url=task.thumbnail_url,
        source_channel_id=task.source_channel_id, source_channel_title=task.source_channel_title,
        target_channel_id=task.target_channel_id, target_channel_title=task.target_channel_title,
        status=task.status, progress=task.progress, error_message=task.error_message,
        privacy_status=task.privacy_status, scheduled_at=task.scheduled_at, created_at=task.created_at,
        started_at=task.started_at, completed_at=task.completed_at
    )
