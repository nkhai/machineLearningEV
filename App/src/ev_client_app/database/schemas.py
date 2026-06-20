from pydantic import BaseModel

class VehicleCreate(BaseModel):
    car_id: str
    car_name: str
    vin_number: str
    license_plate: str
    battery_serial: str
    motor_serial: str
    user_id: str = ""