# state.py

from typing import List, Optional
from pydantic import BaseModel


class StudentProfile(BaseModel):
    score: Optional[float] = None
    subjects: Optional[List[str]] = None
    preferred_major: Optional[str] = None


class ProgramInfo(BaseModel):
    university: str
    program: str
    admission_method: str
    quota: Optional[int] = None
    subject_combination: Optional[List[str]] = None


class AgentState(BaseModel):

    user_query: str

    student_profile: Optional[StudentProfile] = None

    retrieved_programs: List[ProgramInfo] = []

    conflicts: List[str] = []

    advisory: Optional[str] = None