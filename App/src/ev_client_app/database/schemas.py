from pydantic import BaseModel

class VehicleCreate(BaseModel):
    car_id: str
    car_name: str
    vin: str
    license_plate: str
    battery: str
    motor: str