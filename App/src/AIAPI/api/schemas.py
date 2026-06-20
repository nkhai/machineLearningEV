from pydantic import BaseModel, field_validator
from typing import Optional
import re


class TrainRequest(BaseModel):
    HDFS_URL: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "HDFS_URL": "http://hc1-c-0003u.hc.apac.bosch.com:9870"
            }
        }
    }

    @field_validator("HDFS_URL")
    @classmethod
    def validate_hdfs_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("HDFS_URL must not be empty")
        if not re.match(r"^https?://", v):
            raise ValueError("HDFS_URL must start with http:// or https://")
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
