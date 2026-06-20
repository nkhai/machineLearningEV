from sqlalchemy.orm import Session
from . import models
from .cache import registered_cars

def get_vehicle(db: Session, car_id: str):
    return db.query(models.Vehicle).filter(models.Vehicle.car_id == car_id).first()

def create_vehicle(
    db: Session,
    car_id: str,
    car_name: str,
    vin_number: str,
    license_plate: str,
    battery_serial: str,
    motor_serial: str,
    user_id: str = ""
):
    vehicle = models.Vehicle(
        car_id=car_id,
        car_name=car_name,
        vin_number=vin_number,
        license_plate=license_plate,
        battery_serial=battery_serial,
        motor_serial=motor_serial,
        user_id=user_id
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    registered_cars.add(car_id)

    print(f"[DB] Vehicle {car_id} saved to PostgreSQL")

    return vehicle

def update_vehicle(db: Session, car_id: str, car_name: str, vin_number: str, license_plate: str, battery_serial: str, motor_serial: str, user_id: str = ""):
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.car_id == car_id).first()
    if not vehicle:
        return None

    vehicle.car_name = car_name
    vehicle.vin_number = vin_number
    vehicle.license_plate = license_plate
    vehicle.battery_serial = battery_serial
    vehicle.motor_serial = motor_serial
    vehicle.user_id = user_id

    db.commit()
    db.refresh(vehicle)

    registered_cars.add(car_id)  

    print(f"[DB] Vehicle {car_id} updated in PostgreSQL")

    return vehicle

def list_vehicles(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Vehicle).offset(skip).limit(limit).all()