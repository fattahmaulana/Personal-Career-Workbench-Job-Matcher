from typing import List, Optional
from pydantic import BaseModel, Field

class Language(BaseModel):
    language: str
    level: str = "conversational"  # e.g. native, fluent, professional, conversational, basic

class Experience(BaseModel):
    company: str
    position: str
    duration: str = ""
    responsibilities: List[str] = Field(default_factory=list)

class Education(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    year: str = ""

class Skills(BaseModel):
    technical: List[str] = Field(default_factory=list)
    soft: List[str] = Field(default_factory=list)

class Preferences(BaseModel):
    locations: List[str] = Field(default_factory=list)
    work_type: str = "remote"  # remote, onsite, hybrid, any
    salary_expectation: str = ""

class PersonalInfo(BaseModel):
    name: str
    email: str
    phone: str = ""
    location: str = ""
    links: List[str] = Field(default_factory=list)

class UserProfile(BaseModel):
    personal: PersonalInfo
    target_role: str
    preferences: Preferences = Field(default_factory=Preferences)
    deal_breakers: List[str] = Field(default_factory=list)
    languages: List[Language] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    skills: Skills = Field(default_factory=Skills)
    certifications: List[str] = Field(default_factory=list)

class JobMatch(BaseModel):
    title: str
    company: str
    location: str
    source: str  # linkedin | jobstreet | manual
    url: str
    description: str = ""
    fit_score: int = 0
    reason: str = ""
    gaps: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    rejected: bool = False
    rejection_reason: str = ""
    score_breakdown: dict = Field(default_factory=dict)
