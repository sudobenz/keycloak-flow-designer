from pydantic import BaseModel, Field

class LoginInput(BaseModel):
    username: str
    password: str

class InstanceInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    base_url: str
    token_url: str
    client_id: str
    client_secret: str
    verify_tls: bool = True
