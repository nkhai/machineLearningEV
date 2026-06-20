from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from core.database import get_db
from core.models import User, Vehicle, PredictInfo
from core.auth import AUTH_ENABLED, TEMPLATE_USER_ID

router = APIRouter(tags=["vehicles"])


class VehicleCreate(BaseModel):
    car_id: str
    vehicle_name: str
    vin_number: str
    license_plate: Optional[str] = None
    battery_serial: Optional[str] = None
    motor_serial: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "car_id": "EV_001",
                    "vehicle_name": "VinFast VF8",
                    "vin_number": "VIN2026VF8X00001",
                    "license_plate": "51A-12345",
                    "battery_serial": "BAT-VF8-001",
                    "motor_serial": "MOT-VF8-001",
                }
            ]
        }
    }


def _get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Extract the current user from the Azure AD token claims stored in request.state."""
    if not AUTH_ENABLED:
        db_user = db.query(User).filter(User.user_id == TEMPLATE_USER_ID).first()
        if db_user is None:
            raise HTTPException(status_code=404, detail="Template user not found")
        return db_user
    user_obj = getattr(request.state, "user", None)
    if user_obj is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    upn = getattr(user_obj, "claims", {}).get("unique_name", "") or getattr(user_obj, "claims", {}).get("upn", "")
    username = upn.split("@")[0] if "@" in upn else upn
    db_user = db.query(User).filter(User.user_id == username).first()
    if db_user is None:
        name = getattr(user_obj, "claims", {}).get("name", username)
        db_user = User(
            user_id=username,
            user_name=name,
            pw="",
            phone_number=None,
            role="User",
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    return db_user


@router.post("/vehicles", status_code=201)
def create_vehicle(body: VehicleCreate, request: Request, db: Session = Depends(get_db)):
    """Create a new vehicle under the authenticated user."""
    db_user = _get_current_user(request, db)

    if db.query(Vehicle).filter(Vehicle.car_id == body.car_id).first():
        raise HTTPException(status_code=409, detail=f"Vehicle '{body.car_id}' already exists")

    vehicle = Vehicle(
        car_id=body.car_id,
        vehicle_name=body.vehicle_name,
        vin_number=body.vin_number,
        license_plate=body.license_plate,
        battery_serial=body.battery_serial,
        motor_serial=body.motor_serial,
        user_id=db_user.user_id,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return {
        "car_id": vehicle.car_id,
        "vehicle_name": vehicle.vehicle_name,
        "vin_number": vehicle.vin_number,
        "license_plate": vehicle.license_plate,
        "battery_serial": vehicle.battery_serial,
        "motor_serial": vehicle.motor_serial,
        "user_id": vehicle.user_id,
    }


@router.get("/vehicles")
def get_all_vehicles(request: Request, db: Session = Depends(get_db)):
    """Get all vehicles belonging to the authenticated user."""
    db_user = _get_current_user(request, db)
    vehicles = db.query(Vehicle).filter(Vehicle.user_id == db_user.user_id).all()
    return {
        "user_id": db_user.user_id,
        "total": len(vehicles),
        "vehicles": [
            {
                "car_id": v.car_id,
                "vehicle_name": v.vehicle_name,
                "vin_number": v.vin_number,
                "license_plate": v.license_plate,
                "battery_serial": v.battery_serial,
                "motor_serial": v.motor_serial,
            }
            for v in vehicles
        ],
    }


@router.get("/vehicles/{car_id}")
def get_car_info(car_id: str, request: Request, db: Session = Depends(get_db)):
    """Get a specific car's info. The car must belong to the authenticated user."""
    db_user = _get_current_user(request, db)
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.car_id == car_id, Vehicle.user_id == db_user.user_id)
        .first()
    )
    if vehicle is None:
        raise HTTPException(status_code=404, detail=f"Vehicle '{car_id}' not found for user '{db_user.user_id}'")
    return {
        "car_id": vehicle.car_id,
        "vehicle_name": vehicle.vehicle_name,
        "vin_number": vehicle.vin_number,
        "license_plate": vehicle.license_plate,
        "battery_serial": vehicle.battery_serial,
        "motor_serial": vehicle.motor_serial,
        "user_id": vehicle.user_id,
    }


@router.get("/vehicles/{car_id}/predictions")
def get_predictions_by_car(car_id: str, request: Request, db: Session = Depends(get_db)):
    """Get all prediction results for a specific car, sorted by timestamp (newest first)."""
    db_user = _get_current_user(request, db)

    # Ensure the car belongs to the authenticated user
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.car_id == car_id, Vehicle.user_id == db_user.user_id)
        .first()
    )
    if vehicle is None:
        raise HTTPException(status_code=404, detail=f"Vehicle '{car_id}' not found for user '{db_user.user_id}'")

    predictions = (
        db.query(PredictInfo)
        .filter(PredictInfo.car_id == car_id)
        .order_by(PredictInfo.time_stamp.desc())
        .all()
    )
    return {
        "car_id": car_id,
        "vehicle_name": vehicle.vehicle_name,
        "total": len(predictions),
        "predictions": [
            {
                "session_id": p.session_id,
                "max_mileage_km": p.max_mileage_km,
                "prediction_method": p.prediction_method,
                "gt_capacity": p.gt_capacity,
                "pred_xgboost_chg": p.pred_xgboost_chg,
                "pred_xgboost_drv": p.pred_xgboost_drv,
                "final_ensemble_pred": p.final_ensemble_pred,
                "error": p.error,
                "time_stamp": p.time_stamp.isoformat() if p.time_stamp else None,
            }
            for p in predictions
        ],
    }
