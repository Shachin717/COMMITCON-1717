from pydantic import BaseModel, EmailStr


class OtpRequest(BaseModel):
    email: EmailStr
    purpose: str


class OtpVerify(BaseModel):
    email: EmailStr
    purpose: str
    code: str

