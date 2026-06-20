from sqlalchemy import Column, String
from .connection import Base

class Vehicle(Base):
    __tablename__ = "vehicles"

    car_id = Column(String, primary_key=True, index=True)
    car_name = Column(String)
    vin_number = Column(String, unique=True)
    license_plate = Column(String, unique=True)
    battery_serial = Column(String)
    motor_serial = Column(String)
    user_id = Column(String)