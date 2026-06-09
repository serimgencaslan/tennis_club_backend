from sqlalchemy import Column, Integer, String, Boolean, Enum, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import enum

class GenderEnum(str, enum.Enum):
    male = "male"
    female = "female"

class RoleEnum(str, enum.Enum):
    player = "player"
    admin = "admin"

class MatchPostStatus(str, enum.Enum):
    open = "open"
    matched = "matched"
    cancelled = "cancelled"

class MatchStatus(str, enum.Enum):
    scheduled = "scheduled"
    completed = "completed"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True) # Telefon numarası için
    hashed_password = Column(String, nullable=False)
    gender = Column(Enum(GenderEnum), nullable=False)
    category = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.player)
    is_active = Column(Boolean, default=True)
    is_initial_password = Column(Boolean, default=True, nullable=False)
    posts = relationship("MatchPost", back_populates="owner", foreign_keys="MatchPost.owner_id")

class MatchPost(Base):
    __tablename__ = "match_posts"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    opponent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    date = Column(String, nullable=False)
    time_slot = Column(String) #start time
    end_time = Column(String)   # <--- Bu satırı ekle
    category = Column(String, nullable=False)
    match_type = Column(String, nullable=False)
    note = Column(String, nullable=True)
    status = Column(Enum(MatchPostStatus), default=MatchPostStatus.open)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="posts", foreign_keys=[owner_id])
    opponent = relationship("User", foreign_keys=[opponent_id])
    court_id = Column(Integer, ForeignKey("courts.id"), nullable=True) # İlan verilirken seçilen kort
    court = relationship("Court")

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    player1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    player2_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String, nullable=False)
    match_type = Column(String, nullable=False)
    played_at = Column(String, nullable=True)   # "2025-04-10"
    status = Column(Enum(MatchStatus), default=MatchStatus.scheduled)
    # Skor: set bazlı, max 3 set
    p1_set1 = Column(Integer, nullable=True)
    p2_set1 = Column(Integer, nullable=True)
    p1_set2 = Column(Integer, nullable=True)
    p2_set2 = Column(Integer, nullable=True)
    p1_set3 = Column(Integer, nullable=True)
    p2_set3 = Column(Integer, nullable=True)
    # Hesaplanmış
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    p1_points = Column(Integer, default=0)   # kazanan 30, kaybeden 5
    p2_points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    post_id = Column(Integer, ForeignKey("match_posts.id"), nullable=True)

    player1 = relationship("User", foreign_keys=[player1_id])
    player2 = relationship("User", foreign_keys=[player2_id])
    winner = relationship("User", foreign_keys=[winner_id])

    start_time = Column(String, nullable=True) # Maçın saatini tutmak için
    court_id = Column(Integer, ForeignKey("courts.id"), nullable=True) # Kort bilgisini tutmak için

    # İlişkiyi de ekleyelim ki kort ismine erişebilelim
    court = relationship("Court")

class CourtStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"

class ReservationStatus(str, enum.Enum):
    pending = "pending"       # oyuncu talep etti
    approved = "approved"     # admin onayladı
    rejected = "rejected"     # admin reddetti
    cancelled = "cancelled"   # oyuncu iptal etti
    blocked = "blocked"       # bakım/onarım

class Court(Base):
    __tablename__ = "courts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)          # "Kort 1", "Kort 2" vb.
    description = Column(String, nullable=True)    # "Kapalı kort", "Açık kort" vb.
    status = Column(Enum(CourtStatus), default=CourtStatus.active)
    created_at = Column(DateTime, default=datetime.utcnow)
    reservations = relationship("Reservation", back_populates="court")

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True, index=True)
    court_id = Column(Integer, ForeignKey("courts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=True)
    date = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    status = Column(Enum(ReservationStatus), default=ReservationStatus.pending)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    court = relationship("Court", back_populates="reservations")
    user = relationship("User")
    
    # Yeni eklenen ilişki: Maç üzerinden oyunculara erişim sağlar
    match = relationship("Match") 
    
    heating_on = Column(Boolean, default=False)
    lighting_on = Column(Boolean, default=False)

from sqlalchemy import Column, Integer, String, ForeignKey, Date, Time, Boolean, Table
from database import Base

# Grup derslerinde birden fazla öğrenci olabileceği için Many-to-Many ara tablosu
lesson_students = Table(
    "lesson_students",
    Base.metadata,
    Column("lesson_id", Integer, ForeignKey("lessons.id", ondelete="CASCADE")),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"))
)

class Coach(Base):
    __tablename__ = "coaches"
    
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    
    lessons = relationship("Lesson", back_populates="coach")

class Lesson(Base):
    __tablename__ = "lessons"
    
    id = Column(Integer, primary_key=True, index=True)
    court_id = Column(Integer, ForeignKey("courts.id", ondelete="CASCADE"))
    coach_id = Column(Integer, ForeignKey("coaches.id", ondelete="CASCADE"))
    lesson_type = Column(String, nullable=False) # "bireysel" veya "grup"
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    note = Column(String, nullable=True)
    
    # İlişkiler
    coach = relationship("Coach", back_populates="lessons")
    court = relationship("Court") # Kort bilgisi için
    students = relationship("User", secondary=lesson_students)

# models.py dosyasının en altına eklenecek alan:

class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # "attended" (Geldi) veya "absent" (Gelmedi) değerlerini tutacak sütun
    status = Column(String, nullable=False, default="pending") 

    # Opsiyonel: İlişkileri kurarak sorguları kolaylaştırmak isterseniz (Hata verirse eklemeyebilirsiniz)
    lesson = relationship("Lesson", backref="attendance_records")
    student = relationship("User")

# models.py dosyasının en altına eklenecek:

class LessonFee(Base):
    __tablename__ = "lesson_fees"

    id = Column(Integer, primary_key=True, index=True)
    fee_type = Column(String, unique=True, nullable=False) # "bireysel" veya "grup"
    amount = Column(Float, nullable=False, default=0.0) # Ders başına (veya grup için kişi başı) ücret