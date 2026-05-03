"""Family models, memories, holidays, members."""
from typing import List, Optional
from pydantic import BaseModel, Field
from models import new_id, now_iso


class FamilyMember(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    relation: str = ""  # spouse, daughter, son, mother, father, sibling, friend, other
    birthday: Optional[str] = ""  # YYYY-MM-DD
    photo_url: Optional[str] = ""
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)


class FamilyMemberCreate(BaseModel):
    name: str
    relation: str = ""
    birthday: Optional[str] = ""
    photo_url: Optional[str] = ""
    notes: str = ""


class FamilyMemory(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    date: str  # YYYY-MM-DD
    location: str = ""
    story: str = ""
    photo_url: Optional[str] = ""
    member_ids: List[str] = []  # linked family member ids
    tags: List[str] = []
    created_at: str = Field(default_factory=now_iso)


class FamilyMemoryCreate(BaseModel):
    title: str
    date: str
    location: str = ""
    story: str = ""
    photo_url: Optional[str] = ""
    member_ids: List[str] = []
    tags: List[str] = []


class Holiday(BaseModel):
    id: str = Field(default_factory=new_id)
    destination: str
    start_date: str  # YYYY-MM-DD
    end_date: str
    status: str = "planned"  # planned, booked, completed
    budget: str = ""
    notes: str = ""
    todos: List[dict] = []  # [{text, done}]
    photo_urls: List[str] = []
    member_ids: List[str] = []
    created_at: str = Field(default_factory=now_iso)


class HolidayCreate(BaseModel):
    destination: str
    start_date: str
    end_date: str
    status: str = "planned"
    budget: str = ""
    notes: str = ""
    todos: List[dict] = []
    photo_urls: List[str] = []
    member_ids: List[str] = []
