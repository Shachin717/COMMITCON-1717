from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, model_validator

from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    portal: Optional[str] = None


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str
    portal: Optional[str] = None


class VerifyOtpResponse(BaseModel):
    valid: bool = True
    message: str
    reset_token: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str
    otp: Optional[str] = None
    reset_token: Optional[str] = None
    portal: Optional[str] = None

    @model_validator(mode="after")
    def check_otp_or_token(self) -> "ResetPasswordRequest":
        if not self.otp and not self.reset_token:
            raise ValueError("Either 'otp' or 'reset_token' must be provided.")
        if len(self.new_password) < 6:
            raise ValueError("Password must be at least 6 characters long.")
        return self


class ChangePasswordRequest(BaseModel):
    old_password: Optional[str] = None
    new_password: str

    @model_validator(mode="after")
    def check_password_length(self) -> "ChangePasswordRequest":
        if len(self.new_password) < 6:
            raise ValueError("New password must be at least 6 characters long.")
        return self


class MessageResponse(BaseModel):
    message: str
