"""Queue controls share the download cookie, never the Google account identity."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from app.api.downloads import owner, remote, use_remote
from app.database.db import get_session
from app.models.models import DownloadJob
from app.models.download_control_models import DownloadQueueControl, DownloadJobControl
from app.services.download_jobs import get_job, download_queue

router = APIRouter(prefix="/download-controls", tags=["download-controls"])


class PauseRequest(BaseModel):
    paused: bool


class ReorderRequest(BaseModel):
    job_ids: list[str] = Field(min_length=1)


def queue_state(session, owner_id):
    queue = session.get(DownloadQueueControl, owner_id)
    jobs = session.exec(select(DownloadJob).where(DownloadJob.owner_id == owner_id,
                          DownloadJob.status == "queued").order_by(DownloadJob.created_at)).all()
    controls = {row.job_id: row for row in session.exec(select(DownloadJobControl)
                .where(DownloadJobControl.owner_id == owner_id)).all()}
    jobs.sort(key=lambda job: (controls[job.id].position if job.id in controls else -1, job.created_at))
    return {"paused": bool(queue and queue.paused), "job_ids": [job.id for job in jobs]}


def set_pause(session, owner_id, paused):
    queue = session.get(DownloadQueueControl, owner_id) or DownloadQueueControl(owner_id=owner_id)
    queue.paused = paused
    session.add(queue)
    session.commit()
    return queue_state(session, owner_id)


def cancel_job(session, owner_id, job_id):
    with download_queue.create_lock:
        job = get_job(session, job_id, owner_id)
        session.refresh(job)
        if job.status == "cancelled":
            return {"cancelled": True}
        if job.status not in ("queued", "running"):
            raise HTTPException(409, "Somente downloads aguardando ou em andamento podem ser cancelados.")
        control = session.get(DownloadJobControl, job_id) or DownloadJobControl(job_id=job_id, owner_id=owner_id)
        control.cancelled = True
        session.add(control)
        job.status, job.message = "cancelled", "Download cancelado por você."
        session.add(job)
        session.commit()
        return {"cancelled": True}


def reorder_jobs(session, owner_id, job_ids):
    with download_queue.create_lock:
        state = queue_state(session, owner_id)
        if len(set(job_ids)) != len(job_ids) or set(job_ids) != set(state["job_ids"]):
            raise HTTPException(409, "A fila mudou. Atualize antes de alterar a ordem.")
        for position, job_id in enumerate(job_ids):
            control = session.get(DownloadJobControl, job_id) or DownloadJobControl(job_id=job_id, owner_id=owner_id)
            control.position = position
            session.add(control)
        session.commit()
        return queue_state(session, owner_id)


@router.get("")
def state(request: Request, response: Response, session: Session = Depends(get_session)):
    identifier = owner(request, response)
    return remote("GET", "/controls", params={"owner_id": identifier}) if use_remote() else queue_state(session, identifier)


@router.post("/pause")
def pause(payload: PauseRequest, request: Request, response: Response, session: Session = Depends(get_session)):
    identifier = owner(request, response)
    return remote("POST", "/controls/pause", params={"owner_id": identifier}, json=payload.model_dump()) if use_remote() else set_pause(session, identifier, payload.paused)


@router.post("/reorder")
def reorder(payload: ReorderRequest, request: Request, response: Response, session: Session = Depends(get_session)):
    identifier = owner(request, response)
    return remote("POST", "/controls/reorder", params={"owner_id": identifier}, json=payload.model_dump()) if use_remote() else reorder_jobs(session, identifier, payload.job_ids)


@router.post("/jobs/{job_id}/cancel")
def cancel(job_id: str, request: Request, response: Response, session: Session = Depends(get_session)):
    identifier = owner(request, response)
    return remote("POST", f"/controls/jobs/{job_id}/cancel", params={"owner_id": identifier}) if use_remote() else cancel_job(session, identifier, job_id)


def install_worker_routes(app, authorize):
    """Worker routes must sit behind its bearer authentication."""
    worker = APIRouter(prefix="/api/download-worker/controls", dependencies=[Depends(authorize)])

    @worker.get("")
    def worker_state(owner_id: str = Query(pattern=r"^[A-Za-z0-9_-]{43}$"), session: Session = Depends(get_session)):
        return queue_state(session, owner_id)

    @worker.post("/pause")
    def worker_pause(payload: PauseRequest, owner_id: str = Query(pattern=r"^[A-Za-z0-9_-]{43}$"), session: Session = Depends(get_session)):
        return set_pause(session, owner_id, payload.paused)

    @worker.post("/reorder")
    def worker_reorder(payload: ReorderRequest, owner_id: str = Query(pattern=r"^[A-Za-z0-9_-]{43}$"), session: Session = Depends(get_session)):
        return reorder_jobs(session, owner_id, payload.job_ids)

    @worker.post("/jobs/{job_id}/cancel")
    def worker_cancel(job_id: str, owner_id: str = Query(pattern=r"^[A-Za-z0-9_-]{43}$"), session: Session = Depends(get_session)):
        return cancel_job(session, owner_id, job_id)

    app.include_router(worker)
