from pydantic import BaseModel


class RequestData(BaseModel):
    broker_code: str
    pan_no: str