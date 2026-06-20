from sqlalchemy.orm import Session
from . import models
from .cache import registered_cars

def get_vehicle(db: Session, car_id: str):
    return db.query(models.Vehicle).filter(models.Vehicle.car_id == car_id).first()

def create_vehicle(
    db: Session,
    car_id: str,
    car_name: str,
    vin: str,
    license_plate: str,
    battery: str,
    motor: str
):
    vehicle = models.Vehicle(
        car_id=car_id,
        car_name=car_name,
        vin=vin,
        license_plate=license_plate,
        battery=battery,
        motor=motor
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    registered_cars.add(car_id)

    print(f"[DB] Vehicle {car_id} saved to PostgreSQL")

    return vehicle

def update_vehicle(db: Session, car_id: str, car_name: str, vin: str, license_plate: str, battery: str, motor: str):
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.car_id == car_id).first()
    if not vehicle:
        return None

    vehicle.car_name = car_name
    vehicle.vin = vin
    vehicle.license_plate = license_plate
    vehicle.battery = battery
    vehicle.motor = motor

    db.commit()
    db.refresh(vehicle)

    registered_cars.add(car_id)  

    print(f"[DB] Vehicle {car_id} updated in PostgreSQL")

    return vehicle

def list_vehicles(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Vehicle).offset(skip).limit(limit).all()