from sqlalchemy import Column, String, Float
from .connection import Base

class Vehicle(Base):
    __tablename__ = "vehicles"

    car_id = Column(String, primary_key=True, index=True)
    car_name = Column(String)
    vin = Column(String, unique=True)
    license_plate = Column(String, unique=True)
    battery = Column(String)
    motor = Column(String)