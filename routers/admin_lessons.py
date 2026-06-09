from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models
import schemas
from sqlalchemy import and_, or_
from auth import get_current_user

router = APIRouter(prefix="/admin-lessons", tags=["Admin Ders Yönetimi"])

# 1. Antrenör Ekleme
@router.post("/coaches", response_model=schemas.CoachResponse)
def create_coach(coach: schemas.CoachCreate, db: Session = Depends(get_db)):
    db_coach = models.Coach(full_name=coach.full_name, phone=coach.phone)
    db.add(db_coach)
    db.commit()
    db.refresh(db_coach)
    return db_coach

# 2. Antrenörleri Listeleme
@router.get("/coaches", response_model=List[schemas.CoachResponse])
def get_coaches(db: Session = Depends(get_db)):
    return db.query(models.Coach).filter(models.Coach.is_active == True).all()

# 3. Özel/Grup Ders Atama (POST)
from datetime import datetime

from datetime import datetime, time

from datetime import datetime, time

@router.post("/lessons")
def create_lesson(payload: schemas.LessonCreate, db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    
    # 🔐 Yetki Kontrolü
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlemi yapmak için yönetici yetkiniz bulunmamaktadır!"
        )

    # 🚀 1. Gelen Saati Metin (String) Olarak Yakala (Örn: "15:00")
    if hasattr(payload.start_time, "strftime"):
        res_start_str = payload.start_time.strftime("%H:%M")
    else:
        res_start_str = str(payload.start_time)[:5]

    if hasattr(payload.end_time, "strftime"):
        res_end_str = payload.end_time.strftime("%H:%M")
    else:
        res_end_str = str(payload.end_time)[:5]

    # Tarih nesnesini ayır (SQLite için Python date objesi)
    res_date_obj = payload.date

    # 🚀 2. DÜZELTME: Ön yüz takviminin 1 saat ileri kaymasını engellemek için,
    # saatleri veritabanına yazmadan önce arka planda el ile 1 saat geriye çekiyoruz.
    start_hour, start_minute = map(int, res_start_str.split(":"))
    end_hour, end_minute = map(int, res_end_str.split(":"))
    
    # A) Lesson tablosunun zorunlu tuttuğu Python 'time' objelerini üretiyoruz (1 saat dengelenmiş)
    balanced_time_obj_start = time(max(0, start_hour - 1), start_minute)
    balanced_time_obj_end = time(max(0, end_hour - 1), end_minute)

    # B) Reservation tablosunun desteklediği saf String formatını üretiyoruz (1 saat dengelenmiş)
    balanced_str_start = f"{max(0, start_hour - 1):02d}:{start_minute:02d}:00"
    balanced_str_end = f"{max(0, end_hour - 1):02d}:{end_minute:02d}:00"

    # 🚀 3. KAPSAMLI ÇAKIŞMA VE DOLULUK KONTROLÜ
    # Sorguyu dengelenmiş zaman nesneleri/stringleri ile yapıyoruz
    overlapping_reservation = db.query(models.Reservation).filter(
        models.Reservation.court_id == payload.court_id,
        models.Reservation.date == res_date_obj,
        or_(
            and_(models.Reservation.start_time >= balanced_str_start, models.Reservation.start_time < balanced_str_end),
            and_(models.Reservation.end_time > balanced_str_start, models.Reservation.end_time <= balanced_str_end),
            and_(models.Reservation.start_time <= balanced_str_start, models.Reservation.end_time >= balanced_str_end)
        )
    ).first()

    if overlapping_reservation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Seçilen kort ve saat aralığı doludur! Bu saatte kişisel maç rezervasyonu veya başka bir etkinlik bulunmaktadır."
        )

    # 🚀 4. DERS KAYDINI OLUŞTUR (Bu tablo Python 'time' nesnesi istiyor)
    db_lesson = models.Lesson(
        court_id=payload.court_id,
        coach_id=payload.coach_id,
        lesson_type=payload.lesson_type,
        date=res_date_obj,                 # Python date objesi
        start_time=balanced_time_obj_start, # 🕒 Lesson tablosunun istediği Python time objesi
        end_time=balanced_time_obj_end,     # 🕒 Lesson tablosunun istediği Python time objesi
        note=payload.note
    )
    
    # Öğrencileri ilişkilendir (Many-to-Many)
    for student_id in payload.student_ids:
        student = db.query(models.User).filter(models.User.id == student_id).first()
        if student:
            db_lesson.students.append(student)

    db.add(db_lesson)
    db.flush() # Artık veri tipleri tam uyuştuğu için burası hatasız geçecek

    # 🚀 5. KORT REZERVASYON TABLOSUNA ENTROPİ EKLE (Bu tablo görüntündeki gibi saf String istiyor)
    db_reservation = models.Reservation(
        court_id=payload.court_id,
        user_id=current_user.id,  
        date=res_date_obj,      
        start_time=balanced_str_start,   # 🏟️ Görseldeki hatayı çözen saf String zaman formatı ("19:00:00")
        end_time=balanced_str_end,       # 🏟️ Görseldeki hatayı çözen saf String zaman formatı ("20:00:00")
        note=payload.note or f"ÖZEL DERS REZERVASYONU",
        status=models.ReservationStatus.approved,  
        heating_on=False,
        lighting_on=False
    )
    db.add(db_reservation)
    
    try:
        db.commit()
        db.refresh(db_lesson)
        return {"status": "success", "message": "Ders başarıyla planlandı ve kort rezerve edilerek takvim kilitlendi."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ders planlanırken veritabanı hatası oluştu: {str(e)}"
        )
    
# 🚀 4. PLANLANMIŞ DERSLERİ LİSTELEME (GET)
# routers/admin_lessons.py dosyasının en altındaki listeleme endpoint'inin güncel hali
from typing import Optional

@router.get("/lessons")
def get_all_lessons(start_date: Optional[str] = None, end_date: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Lesson)
    
    # Eğer frontend belirli bir haftanın aralığını gönderdiyse veritabanında filtrele
    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(models.Lesson.date >= start_dt, models.Lesson.date <= end_dt)
        except ValueError:
            pass # Tarih formatı hatalıysa filtreleme yapma, hepsini getir
            
    # 🚀 DÜZELTME: .ascii() hatalı kısımları, SQLAlchemy'nin doğru sıralama fonksiyonu olan .asc() ile değiştirildi.
    lessons = query.order_by(models.Lesson.date.asc(), models.Lesson.start_time.asc()).all()
    
    result = []
    for l in lessons:
        # Backend'e 1 saat geri kaydırarak kaydettiğimiz saatleri, 
        # frontend'e verirken orijinal saatine (+1 saat) geri döndürüyoruz.
        def fix_display_time(t_val):
            if not t_val: return None
            t_str = t_val.strftime("%H:%M") if hasattr(t_val, "strftime") else str(t_val)[:5]
            h, m = map(int, t_str.split(":"))
            return f"{(h + 1) % 24:02d}:{m:02d}"

        result.append({
            "id": l.id,
            "lesson_type": l.lesson_type,
            "date": l.date.isoformat() if hasattr(l.date, "isoformat") else str(l.date),
            "start_time": fix_display_time(l.start_time), 
            "end_time": fix_display_time(l.end_time),     
            "note": l.note,
            "court": {"id": l.court.id, "name": l.court.name} if l.court else None,
            "coach": {"id": l.coach.id, "full_name": l.coach.full_name} if l.coach else None,
            "students": [{"id": s.id, "full_name": s.full_name} for s in l.students]
        })
    return result

# routers/admin_lessons.py dosyasının en altına eklenecek alanlar:

@router.get("/lessons-with-attendance")
def get_lessons_with_attendance(start_date: Optional[str] = None, end_date: Optional[str] = None, db: Session = Depends(get_db)):
    """Yoklama sayfasında derslerin yoklama durumlarıyla birlikte listelenmesini sağlar"""
    query = db.query(models.Lesson)
    
    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(models.Lesson.date >= start_dt, models.Lesson.date <= end_dt)
        except ValueError:
            pass
            
    lessons = query.order_by(models.Lesson.date.asc(), models.Lesson.start_time.asc()).all()
    
    result = []
    for l in lessons:
        def fix_display_time(t_val):
            if not t_val: return None
            t_str = t_val.strftime("%H:%M") if hasattr(t_val, "strftime") else str(t_val)[:5]
            h, m = map(int, t_str.split(":"))
            return f"{(h + 1) % 24:02d}:{m:02d}"

        # 🚀 Bu derse ait daha önce girilmiş yoklama var mı kontrol et
        # models.Attendance tablonuzun yapısına göre sorguluyoruz
        saved_attendances = db.query(models.Attendance).filter(models.Attendance.lesson_id == l.id).all()
        attendance_taken = len(saved_attendances) > 0
        
        # Öğrenci id'lerine göre kimlerin gelip gelmediği haritasını çıkar
        attendance_map = {a.student_id: a.status for a in saved_attendances} # Örn: {1: "attended", 2: "absent"}

        result.append({
            "id": l.id,
            "lesson_type": l.lesson_type,
            "date": l.date.isoformat() if hasattr(l.date, "isoformat") else str(l.date),
            "start_time": fix_display_time(l.start_time), 
            "end_time": fix_display_time(l.end_time),     
            "note": l.note,
            "attendance_taken": attendance_taken, # Frontend'de satır rengini değiştirecek bayrak
            "court": {"id": l.court.id, "name": l.court.name} if l.court else None,
            "coach": {"id": l.coach.id, "full_name": l.coach.full_name} if l.coach else None,
            "students": [
                {
                    "id": s.id, 
                    "full_name": s.full_name,
                    "status": attendance_map.get(s.id, "pending") # Daha önce seçilmiş durum veya pending
                } for s in l.students
            ]
        })
    return result

@router.post("/attendance")
def save_attendance(payload: schemas.AttendanceSubmit, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Adminin gönderdiği yoklama listesini kaydeder veya günceller"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Yönetici yetkisi gerekli.")
        
    # Eski yoklama kayıtları varsa mükerrer olmaması için önce temizle (Update mantığı için)
    db.query(models.Attendance).filter(models.Attendance.lesson_id == payload.lesson_id).delete()
    
    # Yeni kayıtları ekle
    for item in payload.records:
        db_att = models.Attendance(
            lesson_id=payload.lesson_id,
            student_id=item.student_id,
            status=item.status # "attended" (Geldi) veya "absent" (Gelmedi)
        )
        db.add(db_att)
        
    try:
        db.commit()
        return {"status": "success", "message": "Yoklama başarıyla kaydedildi."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Yoklama kaydedilirken hata: {str(e)}")

# routers/admin_lessons.py dosyasının en altına eklenecek:

@router.get("/fees")
def get_lesson_fees(db: Session = Depends(get_db)):
    """Sistemdeki güncel bireysel ve grup ders ücretlerini döner"""
    # Varsayılan ücretler yoksa oluştur
    bireysel = db.query(models.LessonFee).filter(models.LessonFee.fee_type == "bireysel").first()
    if not bireysel:
        bireysel = models.LessonFee(fee_type="bireysel", amount=500.0)
        db.add(bireysel)
        
    grup = db.query(models.LessonFee).filter(models.LessonFee.fee_type == "grup").first()
    if not grup:
        grup = models.LessonFee(fee_type="grup", amount=300.0)
        db.add(grup)
    
    db.commit()
    return db.query(models.LessonFee).all()

@router.post("/fees")
def update_lesson_fee(payload: schemas.FeeUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Adminin ders ücretlerini değiştirmesini sağlar"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Yönetici yetkisi gerekli.")
        
    fee = db.query(models.LessonFee).filter(models.LessonFee.fee_type == payload.fee_type).first()
    if not fee:
        fee = models.LessonFee(fee_type=payload.fee_type)
        db.add(fee)
        
    fee.amount = payload.amount
    db.commit()
    return {"status": "success", "message": f"{payload.fee_type} ders ücreti güncellendi."}

@router.get("/finance-summary")
def get_finance_summary(month: int, year: int, db: Session = Depends(get_db)):
    """Seçilen ay ve yıla göre öğrencilerin yoklama tabanlı borç dökümünü hesaplar"""
    
    # 1. Güncel ücret tarifesini çek
    fees = {f.fee_type: f.amount for f in db.query(models.LessonFee).all()}
    bireysel_fee = fees.get("bireysel", 500.0)
    grup_fee = fees.get("grup", 300.0)

    # 2. Tüm öğrencileri (player) çek
    students = db.query(models.User).filter(models.User.role == "player").all()
    
    result = []
    
    for student in students:
        # Bu öğrencinin seçilen ayda 'attended' (Geldi) olarak işaretlendiği yoklama kayıtlarını çek
        attendances = db.query(models.Attendance).join(models.Lesson).filter(
            models.Attendance.student_id == student.id,
            models.Attendance.status == "attended"
        ).all()
        
        # Seçilen aya göre filtrele (Python tarafında)
        monthly_attended_lessons = []
        total_debt = 0.0
        
        for att in attendances:
            # Lesson date kontrolü
            l_date = att.lesson.date
            if l_date and l_date.month == month and l_date.year == year:
                # Ders türüne göre ücreti belirle
                fee_applied = bireysel_fee if att.lesson.lesson_type == "bireysel" else grup_fee
                total_debt += fee_applied
                
                # Detay satırı oluştur (Açıklayıcı olması için)
                def fix_display_time(t_val):
                    if not t_val: return ""
                    t_str = t_val.strftime("%H:%M") if hasattr(t_val, "strftime") else str(t_val)[:5]
                    h, m = map(int, t_str.split(":"))
                    return f"{(h + 1) % 24:02d}:{m:02d}"

                monthly_attended_lessons.append({
                    "lesson_id": att.lesson.id,
                    "date": l_date.isoformat(),
                    "time": f"{fix_display_time(att.lesson.start_time)} - {fix_display_time(att.lesson.end_time)}",
                    "lesson_type": att.lesson.lesson_type,
                    "coach_name": att.lesson.coach.full_name if att.lesson.coach else "Bilinmiyor",
                    "court_name": att.lesson.court.name if att.lesson.court else "Kort Belirtilmedi",
                    "fee": fee_applied
                })
                
        result.append({
            "student_id": student.id,
            "full_name": student.full_name,
            "email": student.email,
            "category": student.category,
            "total_debt": total_debt,
            "attended_count": len(monthly_attended_lessons),
            "details": monthly_attended_lessons # Ücretin nereden geldiğini gösteren şeffaf döküm
        })
        
    return {
        "bireysel_fee_rate": bireysel_fee,
        "grup_fee_rate": grup_fee,
        "data": result
    }