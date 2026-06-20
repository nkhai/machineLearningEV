from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import re


class TrainRequest(BaseModel):
    HDFS_URL: str = Field(
        ...,
        examples=["http://hc1-c-0003u.hc.apac.bosch.com:9870"],
    )
    # ADD THIS FIELD SO API CAN RECEIVE USER ID
    user_id: str = Field(
        default="system_admin", 
        examples=["templateUser"]
    )

    @field_validator("HDFS_URL")
    @classmethod
    def validate_hdfs_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("HDFS_URL must not be empty")
        if not re.match(r"^https?://", v):
            raise ValueError("HDFS_URL must start with http:// or https://")
        return v


class PredictRequest(BaseModel):
    HDFS_URL: str = Field(
        ...,
        examples=["http://hc1-c-0003u.hc.apac.bosch.com:9870"],
    )
    car_ids: List[str] = Field(
        ...,
        examples=[["EV_104", "EV_109"]],
    )
    predict_date: str = Field(
        ...,
        description='Date in YYYYMMDD format, or "latest" to use the newest available file per car.',
        examples=["latest"],
    )
    # ADD THIS FIELD SO API CAN RECEIVE USER ID
    user_id: str = Field(
        default="system_admin", 
        examples=["templateUser"]
    )

    @field_validator("HDFS_URL")
    @classmethod
    def validate_hdfs_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("HDFS_URL must not be empty")
        if not re.match(r"^https?://", v):
            raise ValueError("HDFS_URL must start with http:// or https://")
        return v

    @field_validator("car_ids")
    @classmethod
    def validate_car_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("car_ids must not be empty")
        return v

    @field_validator("predict_date")
    @classmethod
    def validate_predict_date(cls, v: str) -> str:
        v = v.strip()
        if v.lower() != "latest" and not re.match(r"^\d{8}$", v):
            raise ValueError("predict_date must be 'latest' or in YYYYMMDD format")
        return v


class TrainResponse(BaseModel):
    status: str
    message: str
    outputs: dict
    hdfs_url_used: str


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    detail: Optional[str] = None