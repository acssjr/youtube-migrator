import os
from fastapi import APIRouter, Query, HTTPException
from typing import List
from app.config.config import settings

router = APIRouter(prefix="/logs", tags=["logs"])

@router.get("", response_model=List[str])
def get_logs(
    file: str = Query("downloads", description="Log file type: downloads, uploads, errors"),
    limit: int = Query(100, description="Max lines to retrieve")
):
    """Retrieve the tail of log files (downloads.log, uploads.log, errors.log)."""
    filename = f"{file}.log"
    log_file_path = settings.logs_path / filename
    
    if not os.path.exists(log_file_path):
        return [f"Log file {filename} does not exist yet. Perform operations to populate logs."]

    try:
        with open(log_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Return last N lines
            tail_lines = lines[-limit:]
            return [line.strip() for line in tail_lines]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {e}")
