import asyncio
import os
from datetime import datetime
from typing import Optional
from sqlmodel import Session
from loguru import logger

from app.database.db import engine
from app.models.models import MigrationTask, OAuthToken
from app.repositories.task_repository import TaskRepository
from app.repositories.token_repository import TokenRepository
from app.services.downloader_service import DownloaderService
from app.services.youtube_service import YoutubeService

class QueueService:
    _instance: Optional['QueueService'] = None
    _running: bool = False
    _lock = asyncio.Lock()

    def __init__(self):
        self.downloader = DownloaderService()

    @classmethod
    def get_instance(cls) -> 'QueueService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(self):
        """Start the background worker if not already running."""
        if not self._running:
            self._running = True
            asyncio.create_task(self._run_loop())
            logger.info("Background Migration Queue Service started.")

    def stop(self):
        """Stop the background worker."""
        self._running = False
        logger.info("Background Migration Queue Service stopped.")

    async def _run_loop(self):
        """Infinite loop looking for pending tasks to execute sequentially."""
        while self._running:
            try:
                task = self._get_next_pending_task()
                if task:
                    await self._process_task(task.id)
                else:
                    # No pending tasks, sleep for a short duration
                    await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Error in queue execution loop: {e}")
                await asyncio.sleep(5)

    def _get_next_pending_task(self) -> Optional[MigrationTask]:
        """Fetch the next pending migration task from DB."""
        with Session(engine) as session:
            task_repo = TaskRepository(session)
            tasks = task_repo.get_pending_tasks()
            # If the task is scheduled in the future, skip it
            now = datetime.utcnow()
            for task in tasks:
                if task.scheduled_at is None or task.scheduled_at <= now:
                    return task
            return None

    async def _process_task(self, task_id: int):
        """Execute the migration task: download, upload, cleanup."""
        logger.info(f"Processing migration task #{task_id}")
        
        # 1. Initialize session and repositories
        with Session(engine) as session:
            task_repo = TaskRepository(session)
            token_repo = TokenRepository(session)
            
            task = task_repo.get_by_id(task_id)
            if not task:
                return

            task.started_at = datetime.utcnow()
            task.status = "downloading"
            task.progress = 0.0
            task_repo.save(task)

            # Get target channel token
            target_token = token_repo.get_by_channel_id(task.target_channel_id)
            if not target_token:
                task.status = "error"
                task.error_message = f"OAuth credentials not found for destination channel ID: {task.target_channel_id}"
                task.completed_at = datetime.utcnow()
                task_repo.save(task)
                logger.error(task.error_message)
                return
            
            # Save destination channel title for history
            task.target_channel_title = target_token.channel_title
            task_repo.save(task)
            token_data = target_token.token_data

        # 2. Download Phase
        temp_file = None
        try:
            # We run the blocking download inside an executor to keep FastAPI async loop responsive
            loop = asyncio.get_running_loop()
            
            def update_download_progress(pct: float):
                # We need a separate session to update progress dynamically
                with Session(engine) as progress_session:
                    repo = TaskRepository(progress_session)
                    t = repo.get_by_id(task_id)
                    if t:
                        t.progress = pct * 0.5 # Download counts as first 50% of task
                        repo.save(t)
            
            temp_file, video_info = await loop.run_in_executor(
                None, 
                self.downloader.download_video, 
                task.video_id, 
                update_download_progress
            )
            
            with Session(engine) as session:
                task_repo = TaskRepository(session)
                task = task_repo.get_by_id(task_id)
                task.temp_file_path = temp_file
                
                # Auto-populate metadata if not set
                if not task.description and video_info.get("description"):
                    task.description = video_info["description"]
                if not task.tags and video_info.get("tags"):
                    task.tags = ",".join(video_info["tags"])
                if not task.category_id and video_info.get("category_id"):
                    task.category_id = video_info["category_id"]
                if not task.language and video_info.get("language"):
                    task.language = video_info["language"]
                
                task.status = "uploading"
                task.progress = 50.0
                task_repo.save(task)

        except Exception as e:
            logger.error(f"Download failed for video {task.video_id}: {e}")
            with Session(engine) as session:
                task_repo = TaskRepository(session)
                task = task_repo.get_by_id(task_id)
                task.status = "error"
                task.error_message = f"Download failed: {str(e)}"
                task.completed_at = datetime.utcnow()
                task_repo.save(task)
            return

        # 3. Upload Phase
        thumb_temp_path = None
        try:
            loop = asyncio.get_running_loop()
            youtube_service = YoutubeService(token_data)
            
            def update_upload_progress(pct: float):
                with Session(engine) as progress_session:
                    repo = TaskRepository(progress_session)
                    t = repo.get_by_id(task_id)
                    if t:
                        t.progress = 50.0 + (pct * 0.5) # Upload counts as second 50% of task
                        repo.save(t)

            tags_list = [tag.strip() for tag in task.tags.split(",")] if task.tags else []

            # Download thumbnail locally if present
            if task.thumbnail_url:
                try:
                    import urllib.request
                    thumb_temp_path = os.path.join(self.downloader.download_dir, f"{task.video_id}_thumb.jpg")
                    logger.info(f"Downloading thumbnail from {task.thumbnail_url}")
                    urllib.request.urlretrieve(task.thumbnail_url, thumb_temp_path)
                except Exception as e:
                    logger.warning(f"Failed to download thumbnail: {e}")
                    thumb_temp_path = None

            # Perform the actual upload
            new_video_id = await loop.run_in_executor(
                None,
                youtube_service.upload_video,
                temp_file,
                task.title,
                task.description or "",
                task.privacy_status,
                tags_list,
                task.category_id or "22",
                task.language or "pt",
                update_upload_progress
            )

            # Upload custom thumbnail if downloaded successfully
            if new_video_id and thumb_temp_path and os.path.exists(thumb_temp_path):
                try:
                    logger.info(f"Uploading thumbnail for new video {new_video_id}")
                    await loop.run_in_executor(
                        None,
                        youtube_service.update_thumbnail,
                        new_video_id,
                        thumb_temp_path
                    )
                except Exception as e:
                    logger.warning(f"Failed to upload thumbnail: {e}")

            # Add video to target playlist if specified
            if new_video_id and task.target_playlist_id:
                try:
                    logger.info(f"Adding video {new_video_id} to playlist {task.target_playlist_id}")
                    await loop.run_in_executor(
                        None,
                        youtube_service.add_video_to_playlist,
                        task.target_playlist_id,
                        new_video_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to add video {new_video_id} to playlist {task.target_playlist_id}: {e}")

            # Update status to completed
            with Session(engine) as session:
                task_repo = TaskRepository(session)
                task = task_repo.get_by_id(task_id)
                task.status = "completed"
                task.progress = 100.0
                task.completed_at = datetime.utcnow()
                task_repo.save(task)
                
            logger.info(f"Task #{task_id} successfully completed. New Video ID: {new_video_id}")

        except Exception as e:
            logger.error(f"Upload failed for task #{task_id}: {e}")
            with Session(engine) as session:
                task_repo = TaskRepository(session)
                task = task_repo.get_by_id(task_id)
                task.status = "error"
                task.error_message = f"Upload failed: {str(e)}"
                task.completed_at = datetime.utcnow()
                task_repo.save(task)

        # 4. Clean up temporary files
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    logger.info(f"Cleaned up temporary video file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file}: {e}")
            
            if thumb_temp_path and os.path.exists(thumb_temp_path):
                try:
                    os.remove(thumb_temp_path)
                    logger.info(f"Cleaned up temporary thumbnail: {thumb_temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp thumbnail {thumb_temp_path}: {e}")
