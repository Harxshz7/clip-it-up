import uuid
from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    id: uuid.UUID
    clerk_user_id: str
    email: str
