from pydantic import BaseModel, Field


class CredentialsSchema(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class ProfileUpdateSchema(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    email: str = Field(min_length=3, max_length=255)


class PasswordUpdateSchema(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)
    confirm_password: str = Field(min_length=6, max_length=128)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(default="123456", min_length=6, max_length=128)
    role_ids: list[int] = []
    is_active: bool = True
    is_superuser: bool = False


class UserUpdate(BaseModel):
    id: int
    username: str = Field(min_length=1, max_length=32)
    email: str = Field(min_length=3, max_length=255)
    role_ids: list[int] = []
    is_active: bool = True
    is_superuser: bool = False


class ResetPasswordSchema(BaseModel):
    user_id: int
