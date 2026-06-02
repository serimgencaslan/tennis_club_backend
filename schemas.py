from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional, List
from datetime import datetime

class ChangePasswordSchema(BaseModel):
    new_password: str

# 🚀 Giriş yanıtı için özel şema
class Token(BaseModel):
    access_token: str
    token_type: str
    is_initial_password: bool # 👈 Frontend'in bu bilgiyi görebilmesi için buraya ekledik

class GenderEnum(str, Enum):
    male = "male"
    female = "female"

class RoleEnum(str, Enum):
    player = "player"
    admin = "admin"

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str  # 👈 Burası tanımlı olmalı
    password: str
    gender: GenderEnum
    category: str

class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    gender: GenderEnum
    category: str
    role: RoleEnum
    class Config:
        from_attributes = True

class TokenData(BaseModel):
    email: Optional[str] = None

class MatchPostCreate(BaseModel):
    date: str
    time_slot: str
    end_time: str
    category: List[str] 
    match_type: str
    note: Optional[str] = None
    court_id: int
    player1_id: Optional[int] = None  # Yeni: Kişisel kiralama/atama için
    player2_id: Optional[int] = None  # Yeni: Kişisel kiralama/atama için

class ScoreSubmit(BaseModel):
    p1_set1: int
    p2_set1: int
    p1_set2: int
    p2_set2: int
    p1_set3: Optional[int] = None
    p2_set3: Optional[int] = None
    heating_on: Optional[bool] = False  # 🚀 EKLENDİ
    lighting_on: Optional[bool] = False # 🚀 EKLENDİ

class LeaderboardEntry(BaseModel):
    user: UserOut
    played: int
    won: int
    lost: int
    points: int
    win_rate: float

class CourtCreate(BaseModel):
    name: str
    description: Optional[str] = None

class CourtOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: str
    class Config:
        from_attributes = True

class ReservationCreate(BaseModel):
    court_id: int
    date: str
    start_time: str   
    end_time: str     
    match_id: Optional[int] = None
    reservation_type: str  
    note: Optional[str] = None
    heating_on: bool = False
    lighting_on: bool = False

class ReservationUpdateAdmin(BaseModel):
    court_id: int
    date: str
    start_time: str
    end_time: str
    reservation_type: Optional[str] = None
    note: Optional[str] = None
    heating_on: bool 
    lighting_on: bool 

    class Config:
        from_attributes = True

class MatchPostOut(BaseModel):
    id: int
    owner_id: int
    opponent_id: Optional[int] = None
    date: str
    time_slot: str
    end_time: str  
    category: str
    match_type: str
    note: Optional[str] = None
    status: str
    created_at: datetime
    owner: UserOut
    opponent: Optional[UserOut] = None
    court: Optional[CourtOut] = None 

    class Config:
        from_attributes = True

class MatchOut(BaseModel):
    id: int
    player1_id: int
    player2_id: int
    category: str
    match_type: str
    played_at: str
    start_time: Optional[str] = None
    court_id: Optional[int] = None
    status: str
    score: Optional[str] = None
    winner_id: Optional[int] = None
    
    p1_set1: Optional[int] = None
    p2_set1: Optional[int] = None
    p1_set2: Optional[int] = None
    p2_set2: Optional[int] = None
    p1_set3: Optional[int] = None
    p2_set3: Optional[int] = None

    player1: UserOut
    player2: UserOut
    court: Optional[CourtOut] = None

    class Config:
        from_attributes = True

class ReservationOut(BaseModel):
    id: int
    date: str
    start_time: str
    end_time: str
    status: str
    note: Optional[str]
    created_at: datetime
    court: CourtOut
    requester: Optional[UserOut] = None
    match: Optional[MatchOut] = None
    class Config:
        from_attributes = True

class AdminDirectMatchCreate(BaseModel):
    player1_id: int
    player2_id: int
    court_id: int
    date: str
    start_time: str
    end_time: str
    match_type: str = "single"
    note: Optional[str] = None