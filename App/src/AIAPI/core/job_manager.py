"""
Job manager for long-running ML pipelines.
Uses ThreadPoolExecutor to run tasks in background without blocking the API.
Includes ReadWriteLock to prevent HDFS lease conflicts on model files.
Persists completed sessions to PostgreSQL.
"""
import os
import uuid
import threading
import logging
import pendulum
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Optional

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# ReadWriteLock: allows concurrent reads, exclusive writes
# ══════════════════════════════════════════════════════════════
class ReadWriteLock:
    """
    Multiple readers can hold the lock simultaneously.
    Only one writer can hold the lock, and no readers may hold it during write.
    """
    def __init__(self):
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0
        self._writers = 0
        self._write_waiting = 0

    def acquire_read(self):
        with self._read_ready:
            while self._writers > 0 or self._write_waiting > 0:
                self._read_ready.wait()
            self._readers += 1

    def release_read(self):
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self):
        with self._read_ready:
            self._write_waiting += 1
            while self._readers > 0 or self._writers > 0:
                self._read_ready.wait()
            self._write_waiting -= 1
            self._writers += 1

    def release_write(self):
        with self._read_ready:
            self._writers -= 1
            self._read_ready.notify_all()


# Global lock for model read/write coordination
model_lock = ReadWriteLock()


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobInfo:
    def __init__(self, job_id: str, job_type: str, hdfs_url: str, user_id: str = ""):
        self.job_id = job_id
        self.job_type = job_type
        self.hdfs_url = hdfs_url
        self.user_id = user_id
        self.status = JobStatus.PENDING
        self.message = "Job queued"
        self.progress = ""
        self.result = None
        self.error = None
        self.created_at = pendulum.now("Asia/Ho_Chi_Minh").to_iso8601_string()
        self.started_at = None
        self.completed_at = None

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "user_id": self.user_id,
            "status": self.status.value,
            "message": self.message,
            "progress": self.progress,
            "hdfs_url": self.hdfs_url,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }


MAX_WORKERS = int(os.getenv("MAX_WORKERS", "2"))

# Global executor and job store
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
_jobs: dict = {}


def _persist_session(job: JobInfo):
    """Save completed/failed job to PostgreSQL sessions table."""
    from core.database import SessionLocal
    from core.models import PredictSession, PredictInfo, Vehicle

    db = SessionLocal()
    try:
        result = job.result if isinstance(job.result, dict) else {}

        session_record = PredictSession(
            job_id=job.job_id,
            job_type=job.job_type,
            user_id=job.user_id or None,
            status=job.status.value,
            message=job.message,
            progress=job.progress,
            hdfs_url=job.hdfs_url,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            result_csv_directory=result.get("result_csv_directory"),
            models_loaded_from=result.get("models_loaded_from"),
            metrics=result.get("metrics"),
            saved_files=result.get("saved_files"),
            error=job.error,
        )

        # Link predicted cars to session (only those registered in vehicles table)
        cars_predicted = result.get("cars_predicted", [])
        if cars_predicted:
            vehicles = db.query(Vehicle).filter(Vehicle.car_id.in_(cars_predicted)).all()
            session_record.vehicles = vehicles

        db.add(session_record)
        db.flush()

        # Save per-car prediction details to predict_infos table
        predictions = result.get("predictions", [])
        for pred in predictions:
            car_id = pred.get("car_id")
            # Only save if vehicle exists in DB
            if car_id and db.query(Vehicle).filter(Vehicle.car_id == car_id).first():
                db.add(PredictInfo(
                    car_id=car_id,
                    session_id=job.job_id,
                    max_mileage_km=pred.get("max_mileage_km"),
                    prediction_method=pred.get("prediction_method"),
                    gt_capacity=pred.get("gt_capacity"),
                    pred_xgboost_chg=pred.get("pred_xgboost_chg"),
                    pred_xgboost_drv=pred.get("pred_xgboost_drv"),
                    final_ensemble_pred=pred.get("final_ensemble_pred"),
                    error=pred.get("error"),
                ))

        db.commit()
        log.info("Persisted session %s with %d predictions to DB", job.job_id, len(predictions))
    except Exception as e:
        db.rollback()
        log.error("Failed to persist session %s: %s", job.job_id, e)
    finally:
        db.close()


def submit_job(job_type: str, hdfs_url: str, target_func, *args, user_id: str = "", **kwargs) -> JobInfo:
    """Submit a long-running job to the thread pool."""
    job_id = str(uuid.uuid4())
    job = JobInfo(job_id=job_id, job_type=job_type, hdfs_url=hdfs_url, user_id=user_id)
    _jobs[job_id] = job

    def _wrapper():
        job.status = JobStatus.RUNNING
        job.started_at = pendulum.now("Asia/Ho_Chi_Minh").to_iso8601_string()
        job.message = "Pipeline is running..."
        try:
            result = target_func(job, *args, **kwargs)
            job.status = JobStatus.COMPLETED
            job.message = "Pipeline completed successfully"
            job.result = result
        except Exception as e:
            job.status = JobStatus.FAILED
            job.message = f"Pipeline failed: {str(e)}"
            job.error = str(e)
        finally:
            job.completed_at = pendulum.now("Asia/Ho_Chi_Minh").to_iso8601_string()
            _persist_session(job)

    _executor.submit(_wrapper)
    return job


def get_job(job_id: str) -> Optional[JobInfo]:
    """Get job info by ID. Checks in-memory first, then DB."""
    job = _jobs.get(job_id)
    if job:
        return job
    # Fallback: load from DB (historical session)
    from core.database import SessionLocal
    from core.models import PredictSession
    db = SessionLocal()
    try:
        record = db.query(PredictSession).filter(PredictSession.job_id == job_id).first()
        if record:
            return _session_to_jobinfo(record)
    finally:
        db.close()
    return None


def get_all_jobs() -> list:
    """Get all jobs sorted by creation time (newest first). Merges in-memory + DB."""
    from core.database import SessionLocal
    from core.models import PredictSession
    # In-memory jobs (active/recent)
    in_memory_ids = set(_jobs.keys())
    result = list(_jobs.values())
    # DB sessions not already in memory
    db = SessionLocal()
    try:
        db_sessions = db.query(PredictSession).all()
        for record in db_sessions:
            if record.job_id not in in_memory_ids:
                result.append(_session_to_jobinfo(record))
    finally:
        db.close()
    return sorted(result, key=lambda j: j.created_at, reverse=True)


def get_jobs_for_user(car_ids: set[str]) -> list:
    """Get jobs whose predicted cars overlap with the given car_ids."""
    from core.database import SessionLocal
    from core.models import PredictSession, session_vehicles
    # In-memory active jobs
    in_memory_ids = set()
    result = []
    for job in _jobs.values():
        in_memory_ids.add(job.job_id)
        if job.result and isinstance(job.result, dict):
            predicted = set(job.result.get("cars_predicted", []))
            if predicted & car_ids:
                result.append(job)
        elif job.user_id and job.status in (JobStatus.PENDING, JobStatus.RUNNING):
            result.append(job)
    # DB sessions linked to user's vehicles
    db = SessionLocal()
    try:
        db_sessions = (
            db.query(PredictSession)
            .join(session_vehicles)
            .filter(session_vehicles.c.car_id.in_(car_ids))
            .all()
        )
        for record in db_sessions:
            if record.job_id not in in_memory_ids:
                result.append(_session_to_jobinfo(record))
    finally:
        db.close()
    return sorted(result, key=lambda j: j.created_at, reverse=True)


def _session_to_jobinfo(record) -> JobInfo:
    """Convert a PredictSession DB record to a JobInfo object."""
    job = JobInfo(
        job_id=record.job_id,
        job_type=record.job_type,
        hdfs_url=record.hdfs_url or "",
        user_id=record.user_id or "",
    )
    job.status = JobStatus(record.status)
    job.message = record.message or ""
    job.progress = record.progress or ""
    job.created_at = record.created_at or ""
    job.started_at = record.started_at
    job.completed_at = record.completed_at
    job.error = record.error
    # Reconstruct result dict
    job.result = {
        "result_csv_directory": record.result_csv_directory,
        "models_loaded_from": record.models_loaded_from,
        "cars_predicted": [v.car_id for v in record.vehicles],
        "metrics": record.metrics or {},
        "saved_files": record.saved_files or [],
    }
    return job
