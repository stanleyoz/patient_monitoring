from pydantic import BaseModel
from typing import List
from datetime import datetime

class SessionConfig(BaseModel):
    session_name: str
    researcher_id: str
    participant_id: str
    selected_imus: List[str]
    timestamp: datetime = None
