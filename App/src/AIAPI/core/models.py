from sqlalchemy import String, ForeignKey, JSON, Column, Table, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from core.database import Base


# ── Association table: Session ↔ Vehicle (many-to-many) ──
session_vehicles = Table(
    "session_vehicles",
    Base.metadata,
    Column("job_id", String, ForeignKey("sessions.job_id"), primary_key=True),
    Column("car_id", String, ForeignKey("vehicles.car_id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_name: Mapped[str] = mapped_column(String, nullable=False)
    pw: Mapped[str] = mapped_column(String, nullable=False)
    phone_number: Mapped[str] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False, default="User")  # "Admin" or "User"

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="owner")


class Vehicle(Base):
    __tablename__ = "vehicles"

    car_id: Mapped[str] = mapped_column(String, primary_key=True)
    vehicle_name: Mapped[str] = mapped_column(String, nullable=False)
    vin_number: Mapped[str] = mapped_column(String, nullable=False)
    license_plate: Mapped[str] = mapped_column(String, nullable=True)
    battery_serial: Mapped[str] = mapped_column(String, nullable=True)
    motor_serial: Mapped[str] = mapped_column(String, nullable=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.user_id"), nullable=False)

    owner: Mapped["User"] = relationship(back_populates="vehicles")
    sessions: Mapped[list["PredictSession"]] = relationship(
        secondary=session_vehicles, back_populates="vehicles"
    )
    predict_info: Mapped["PredictInfo"] = relationship(back_populates="vehicle", uselist=False)


class PredictSession(Base):
    """Stores completed predict/train job info persistently."""
    __tablename__ = "sessions"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.user_id"), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=True)
    progress: Mapped[str] = mapped_column(String, nullable=True)
    hdfs_url: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=True)
    started_at: Mapped[str] = mapped_column(String, nullable=True)
    completed_at: Mapped[str] = mapped_column(String, nullable=True)
    result_csv_directory: Mapped[str] = mapped_column(String, nullable=True)
    models_loaded_from: Mapped[str] = mapped_column(String, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=True)
    saved_files: Mapped[list] = mapped_column(JSON, nullable=True)
    error: Mapped[str] = mapped_column(String, nullable=True)

    # Relationships
    owner: Mapped["User"] = relationship()
    vehicles: Mapped[list["Vehicle"]] = relationship(
        secondary=session_vehicles, back_populates="sessions"
    )
    predict_infos: Mapped[list["PredictInfo"]] = relationship(back_populates="session")


class PredictInfo(Base):
    """Per-vehicle prediction result from a session. 1 vehicle has 1 predict info per session."""
    __tablename__ = "predict_infos"

    car_id: Mapped[str] = mapped_column(String, ForeignKey("vehicles.car_id"), primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.job_id"), primary_key=True)
    max_mileage_km: Mapped[str] = mapped_column(String, nullable=True)
    prediction_method: Mapped[str] = mapped_column(String, nullable=True)
    gt_capacity: Mapped[str] = mapped_column(String, nullable=True)
    pred_xgboost_chg: Mapped[str] = mapped_column(String, nullable=True)
    pred_xgboost_drv: Mapped[str] = mapped_column(String, nullable=True)
    final_ensemble_pred: Mapped[str] = mapped_column(String, nullable=True)
    error: Mapped[str] = mapped_column(String, nullable=True)
    time_stamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    vehicle: Mapped["Vehicle"] = relationship(back_populates="predict_info")
    session: Mapped["PredictSession"] = relationship(back_populates="predict_infos")
