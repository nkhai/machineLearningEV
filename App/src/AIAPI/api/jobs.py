from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session
from core.job_manager import get_job, get_all_jobs, get_jobs_for_user
from core.database import get_db
from core.models import User, Vehicle
from core.auth import AUTH_ENABLED, TEMPLATE_USER_ID

router = APIRouter()


def _get_current_user(request: Request, db: Session = Depends(get_db)):
    """Extract the current user from the Azure AD token claims stored in request.state."""
    if not AUTH_ENABLED:
        return db.query(User).filter(User.user_id == TEMPLATE_USER_ID).first()
    user_obj = getattr(request.state, "user", None)
    if user_obj is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Azure AD v1.0 tokens use 'unique_name' (e.g. vkn1hc@bosch.com)
    upn = getattr(user_obj, "claims", {}).get("unique_name", "") or getattr(user_obj, "claims", {}).get("upn", "")
    username = upn.split("@")[0] if "@" in upn else upn
    db_user = db.query(User).filter(User.user_id == username).first()
    return db_user


@router.get("/jobs")
def list_jobs(request: Request, db: Session = Depends(get_db)):
    """List jobs. Admin sees all; regular user sees only jobs for their vehicles."""
    db_user = _get_current_user(request, db)

    if db_user and db_user.role == "Admin":
        jobs = get_all_jobs()
    else:
        if db_user:
            car_ids = {v.car_id for v in db_user.vehicles}
        else:
            car_ids = set()
        jobs = get_jobs_for_user(car_ids) if car_ids else []

    return {
        "total": len(jobs),
        "jobs": [j.to_dict() for j in jobs],
    }


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, request: Request, db: Session = Depends(get_db)):
    """Get the status and progress of a specific job (role-filtered)."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    db_user = _get_current_user(request, db)

    # Admin can see any job
    if db_user and db_user.role == "Admin":
        return job.to_dict()

    # Regular user: only if the job's predicted cars overlap with their vehicles
    if db_user:
        car_ids = {v.car_id for v in db_user.vehicles}
    else:
        car_ids = set()

    if job.result and isinstance(job.result, dict):
        predicted = set(job.result.get("cars_predicted", []))
        if predicted & car_ids:
            return job.to_dict()

    raise HTTPException(status_code=403, detail="You don't have access to this job")
