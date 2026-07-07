from typing import List, Optional
from sqlmodel import Session, select, desc
from app.models.models import MigrationTask

class TaskRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(self, limit: int = 100) -> List[MigrationTask]:
        statement = select(MigrationTask).order_by(desc(MigrationTask.created_at)).limit(limit)
        return self.session.exec(statement).all()

    def get_by_id(self, task_id: int) -> Optional[MigrationTask]:
        return self.session.get(MigrationTask, task_id)

    def get_pending_tasks(self) -> List[MigrationTask]:
        statement = select(MigrationTask).where(MigrationTask.status == "pending").order_by(MigrationTask.created_at)
        return self.session.exec(statement).all()

    def save(self, task: MigrationTask) -> MigrationTask:
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def update_status(self, task_id: int, status: str, progress: float = 0.0, error_message: Optional[str] = None) -> Optional[MigrationTask]:
        task = self.get_by_id(task_id)
        if task:
            task.status = status
            task.progress = progress
            if error_message:
                task.error_message = error_message
            self.save(task)
        return task
