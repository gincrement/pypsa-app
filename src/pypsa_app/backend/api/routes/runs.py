"""Workflow run routes."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path as PathParam
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import get_db, require_permission
from pypsa_app.backend.models import Permission, Run, RunStatus, User, UserRole
from pypsa_app.backend.schemas.auth import UserPublicResponse
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.run import (
    RunCreate,
    RunListResponse,
    RunResponse,
)
from pypsa_app.backend.services.run import SmkExecutorClient
from pypsa_app.backend.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}


def _get_smk_client() -> SmkExecutorClient:
    """Return SmkExecutorClient or raise 503 if not configured."""
    if not settings.smk_executor_url:
        raise HTTPException(503, "Run service is not configured")
    return SmkExecutorClient(settings.smk_executor_url)


def _can_access(user: User | None, run: Run) -> bool:
    """Check if user can view this run."""
    if not settings.enable_auth:
        return True
    if run.user_id is None:
        return True
    if user is None:
        return False
    if user.role == UserRole.ADMIN:
        return True
    return run.user_id == user.id


def _can_modify(user: User | None, run: Run) -> bool:
    """Check if user can cancel/remove this run."""
    if not settings.enable_auth:
        return True
    if user is None:
        return False
    if user.role == UserRole.ADMIN:
        return True
    return run.user_id is not None and run.user_id == user.id


def _check_run_or_404(run_id: uuid.UUID, db: Session, user: User | None) -> Run:
    """Load run record with access check."""
    run = (
        db.query(Run)
        .options(joinedload(Run.owner))
        .filter(Run.job_id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(404, "Run not found")
    if not _can_access(user, run):
        raise HTTPException(404, "Run not found")
    return run


def _sync_run_from_job(run: Run, job: dict, db: Session) -> None:
    """Update a Run record from a smk-executor response dict.

    Only writes fields that changed. Flushes only if something changed.
    """
    changed = False
    field_map = {
        "workflow": "workflow",
        "configfile": "configfile",
        "git_ref": "git_ref",
        "git_sha": "git_sha",
        "exit_code": "exit_code",
        "started_at": "started_at",
        "completed_at": "completed_at",
    }
    for db_field, job_key in field_map.items():
        new_val = job.get(job_key)
        if new_val is not None and getattr(run, db_field) != new_val:
            setattr(run, db_field, new_val)
            changed = True

    # Status needs enum conversion
    raw_status = job.get("status")
    if raw_status:
        try:
            new_status = RunStatus(raw_status)
        except ValueError:
            new_status = None
        if new_status and run.status != new_status:
            run.status = new_status
            changed = True

    if changed:
        db.flush()


def _run_to_response(run: Run) -> RunResponse:
    """Build RunResponse from a local Run record."""
    return RunResponse(
        id=str(run.job_id),
        workflow=run.workflow,
        configfile=run.configfile,
        git_ref=run.git_ref,
        git_sha=run.git_sha,
        status=run.status.value if run.status else "PENDING",
        exit_code=run.exit_code,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        owner=(UserPublicResponse.model_validate(run.owner) if run.owner else None),
    )


@router.post("/", response_model=RunResponse, status_code=201)
def create_run(
    body: RunCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_CREATE)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> RunResponse:
    """Submit a new run."""
    payload = body.model_dump(exclude_none=True)
    result = smk_client.submit_job(payload)

    run = Run(
        job_id=result["job_id"],
        user_id=user.id if user else None,
        workflow=result.get("workflow", body.workflow),
        configfile=result.get("configfile", body.configfile),
        snakemake_args=body.snakemake_args,
        status=RunStatus(result.get("status", "PENDING")),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    logger.info(
        "Run created",
        extra={
            "run_id": result["job_id"],
            "user": user.username if user else "anonymous",
        },
    )

    return RunResponse(
        id=result["job_id"],
        workflow=run.workflow,
        configfile=run.configfile,
        status=run.status.value,
        created_at=run.created_at,
        owner=(UserPublicResponse.model_validate(user) if user else None),
    )


@router.get("/", response_model=RunListResponse)
def list_runs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> RunListResponse:
    """List runs visible to the current user."""
    query = db.query(Run).options(joinedload(Run.owner))
    if settings.enable_auth and user is not None and user.role != UserRole.ADMIN:
        query = query.filter((Run.user_id == user.id) | (Run.user_id.is_(None)))

    total = query.count()
    runs = query.order_by(Run.created_at.desc()).offset(skip).limit(limit).all()

    # Sync non-terminal runs in this page from smk-executor
    non_terminal = [r for r in runs if r.status not in TERMINAL_STATUSES]
    if non_terminal:
        try:
            all_jobs = smk_client.list_jobs()
            jobs_by_id = {j["job_id"]: j for j in all_jobs}

            for run in non_terminal:
                job = jobs_by_id.get(str(run.job_id))
                if job:
                    _sync_run_from_job(run, job, db)

            db.commit()
        except HTTPException:
            # smk-executor unreachable, serve from DB only
            pass

    return RunListResponse(
        data=[_run_to_response(r) for r in runs],
        meta={"total": total, "skip": skip, "limit": limit, "count": len(runs)},
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> RunResponse:
    """Get run detail."""
    run = _check_run_or_404(run_id, db, user)

    # Sync from smk-executor if not in terminal state
    if run.status not in TERMINAL_STATUSES:
        try:
            job = smk_client.get_job(str(run_id))
            _sync_run_from_job(run, job, db)
            db.commit()
        except HTTPException:
            # smk-executor unreachable or job already garbage
            # collected, fall back to local DB
            pass

    return _run_to_response(run)


@router.get("/{run_id}/logs")
def stream_run_logs(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> StreamingResponse:
    """Stream live logs via SSE."""
    _check_run_or_404(run_id, db, user)
    return StreamingResponse(
        smk_client.subscribe_job_logs(str(run_id)),
        media_type="text/event-stream",
    )


@router.get("/{run_id}/outputs")
def list_run_outputs(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> list[dict]:
    """List output files for a completed run."""
    _check_run_or_404(run_id, db, user)
    return smk_client.get_job_outputs(str(run_id))


@router.get("/{run_id}/outputs/{path:path}")
def download_run_output(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    path: str = PathParam(..., description="File path relative to work directory"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_VIEW)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> StreamingResponse:
    """Download an output file."""
    _check_run_or_404(run_id, db, user)
    return StreamingResponse(
        smk_client.download_job_output(str(run_id), path),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{path.rsplit("/", 1)[-1]}"'
        },
    )


@router.post("/{run_id}/cancel", response_model=MessageResponse)
def cancel_run(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_MODIFY)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> dict:
    """Cancel a running run. Keeps the record visible."""
    run = _check_run_or_404(run_id, db, user)
    if not _can_modify(user, run):
        raise HTTPException(403, "You don't have permission to cancel this run")

    try:
        result = smk_client.cancel_job(str(run_id))
        _sync_run_from_job(run, result, db)
        db.commit()
    except HTTPException as e:
        if e.status_code in (404, 409):
            if run.status not in TERMINAL_STATUSES:
                run.status = RunStatus.CANCELLED
                db.commit()
        else:
            raise

    logger.info(
        "Run cancelled",
        extra={
            "run_id": str(run_id),
            "user": user.username if user else "anonymous",
        },
    )

    return {"message": "Run cancelled"}


@router.delete("/{run_id}", response_model=MessageResponse)
def remove_run(
    run_id: uuid.UUID = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUNS_MODIFY)),
    smk_client: SmkExecutorClient = Depends(_get_smk_client),
) -> dict:
    """Remove a run, cancel if still active, and delete the DB row."""
    run = _check_run_or_404(run_id, db, user)
    if not _can_modify(user, run):
        raise HTTPException(403, "You don't have permission to remove this run")

    db.delete(run)
    db.commit()

    # Try to clean up remotely but don't fail the request if it errors
    try:
        smk_client.delete_job(str(run_id))
    except Exception:
        logger.warning("Remote cleanup failed for run %s", run_id, exc_info=True)

    logger.info(
        "Run removed",
        extra={
            "run_id": str(run_id),
            "user": user.username if user else "anonymous",
        },
    )

    return {"message": "Run removed"}
