from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
import models, schemas
from datetime import datetime, timedelta, date 
from typing import Optional
from sqlalchemy import and_

router = APIRouter(prefix="/reservations", tags=["reservations"])

# ── YARDIMCI FONKSİYONLAR ─────────────────────────────────────

def _minutes(t: str) -> int:
    """Zamanı (HH:MM) dakika cinsine çevirir."""
    try:
        h, m = map(int, t.split(":"))
        return h * 60 + m
    except:
        return 0

def _overlaps(s1, e1, s2, e2) -> bool:
    """İki zaman aralığının çakışıp çakışmadığını kontrol eder."""
    return _minutes(s1) < _minutes(e2) and _minutes(e1) > _minutes(s2)

# ── KORT YÖNETİMİ ─────────────────────────────────────────────

@router.get("/courts", response_model=list[schemas.CourtOut])
def get_courts(db: Session = Depends(get_db)):
    """Aktif kortları listeler."""
    return db.query(models.Court).filter(models.Court.status == models.CourtStatus.active).all()

@router.post("/courts", response_model=schemas.CourtOut)
def create_court(data: schemas.CourtCreate, db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Sadece admin kort ekleyebilir")
    court = models.Court(name=data.name)
    db.add(court)
    db.commit()
    db.refresh(court)
    return court

@router.delete("/courts/{court_id}")
def delete_court(court_id: int, db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Yetki yok")
    court = db.query(models.Court).filter(models.Court.id == court_id).first()
    if not court:
        raise HTTPException(status_code=404, detail="Kort bulunamadı")
    
    court.status = models.CourtStatus.inactive 
    db.commit()
    return {"message": "Kort silindi"}

# ── MÜSAİTLİK VE TAKVİM ───────────────────────────────────────

@router.get("/weekly-availability")
def get_weekly_availability(start_date: str, db: Session = Depends(get_db)):
    """Haftalık programı tüm kortlar ve türlerle birlikte döner."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    days = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    courts = db.query(models.Court).filter(models.Court.status == models.CourtStatus.active).all()
    
    result = []
    for day in days:
        day_data = {"date": day, "courts": []}
        for court in courts:
            res_list = db.query(models.Reservation).filter(
                models.Reservation.date == day,
                models.Reservation.court_id == court.id,
                models.Reservation.status.in_(["approved", "pending", "blocked"]) 
            ).all()
            
            day_data["courts"].append({
                "id": court.id,
                "name": court.name,
                "reservations": [
                    {
                        "id": r.id,
                        "start": r.start_time, 
                        "end": r.end_time, 
                        "title": r.note if r.note else r.requester.full_name,
                        "status": r.status
                    } for r in res_list
                ]
            })
        result.append(day_data)
    return result

# ── REZERVASYON İŞLEMLERİ ─────────────────────────────────────

@router.post("", response_model=schemas.ReservationOut)
def create_reservation(data: schemas.ReservationCreate,
                       db: Session = Depends(get_db),
                       current_user: models.User = Depends(get_current_user)):
    
    duration = _minutes(data.end_time) - _minutes(data.start_time)
    if duration <= 0:
        raise HTTPException(status_code=400, detail="Bitiş saati başlangıçtan sonra olmalı")
    
    if current_user.role != models.RoleEnum.admin and duration > 120:
        raise HTTPException(status_code=400, detail="Maksimum rezervasyon süresi 2 saattir.")

    admin_only_types = ["ders", "arıza"]
    if data.reservation_type in admin_only_types and current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Bu türü seçmek için admin yetkisi gerekir.")

    existing = db.query(models.Reservation).filter(
        models.Reservation.court_id == data.court_id,
        models.Reservation.date == data.date,
        models.Reservation.status.in_(["approved", "pending", "blocked"])
    ).all()

    for r in existing:
        if _overlaps(data.start_time, data.end_time, r.start_time, r.end_time):
            raise HTTPException(status_code=409, detail="Bu saatlerde kort dolu.")

    final_status = models.ReservationStatus.approved
    if data.reservation_type == "arıza":
        final_status = models.ReservationStatus.blocked

    type_label = data.reservation_type.upper()
    prefix = f"[{type_label}] "
    
    current_note = data.note if data.note else ""
    final_note = f"{prefix}{current_note}" if not current_note.startswith("[") else current_note

    res = models.Reservation(
        court_id=data.court_id,
        user_id=current_user.id,
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        note=final_note,
        status=final_status
    )
    
    db.add(res)
    db.commit()
    db.refresh(res)
    return res

@router.put("/{res_id}", response_model=schemas.ReservationOut)
def update_reservation_admin(res_id: int, data: schemas.ReservationUpdateAdmin, 
                             db: Session = Depends(get_db),
                             current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Yetkisiz işlem")

    res = db.query(models.Reservation).filter(models.Reservation.id == res_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı")

    conflict = db.query(models.Reservation).filter(
        models.Reservation.id != res_id,
        models.Reservation.court_id == data.court_id,
        models.Reservation.date == data.date,
        models.Reservation.status.in_(["approved", "blocked", "pending"]),
        models.Reservation.start_time < data.end_time,
        models.Reservation.end_time > data.start_time
    ).first()

    if conflict:
        raise HTTPException(status_code=409, detail="Seçilen saatlerde kort dolu")

    updated_note = data.note if data.note else ""
    if hasattr(data, 'reservation_type') and data.reservation_type:
        type_label = data.reservation_type.upper()
        if not updated_note.startswith("["):
            updated_note = f"[{type_label}] {updated_note}"

    res.court_id = data.court_id
    res.date = data.date
    res.start_time = data.start_time
    res.end_time = data.end_time
    res.note = updated_note
    
    res.heating_on = data.heating_on if data.heating_on is not None else res.heating_on
    res.lighting_on = data.lighting_on if data.lighting_on is not None else res.lighting_on
    
    if res.match_id and res.match:
        res.match.played_at = data.date
        res.match.start_time = data.start_time

    try:
        db.commit() 
        db.refresh(res) 
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Veritabanı güncelleme hatası")

    return res

@router.delete("/{res_id}")
def cancel_reservation(res_id: int, db: Session = Depends(get_db),
                       current_user: models.User = Depends(get_current_user)):
    res = db.query(models.Reservation).filter(models.Reservation.id == res_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı")
    
    if res.user_id != current_user.id and current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Yetki yok")
        
    if res.match_id:
        linked_match = db.query(models.Match).filter(models.Match.id == res.match_id).first()
        if linked_match:
            if linked_match.post_id:
                linked_post = db.query(models.MatchPost).filter(models.MatchPost.id == linked_match.post_id).first()
                if linked_post:
                    linked_post.status = models.MatchPostStatus.open
                    linked_post.opponent_id = None 

            db.delete(linked_match) 

    res.status = models.ReservationStatus.cancelled
    db.commit()
    return {"message": "İptal edildi ve ilişkili maç süreçleri temizlendi"}

# ── ADMİN ONAY SİSTEMİ ─────────────────────────────────────────

@router.get("/admin/all", response_model=list[schemas.ReservationOut])
def admin_get_all(db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Sadece admin")
    return db.query(models.Reservation).order_by(models.Reservation.date.desc()).all()

@router.patch("/{res_id}/approve", response_model=schemas.ReservationOut)
def approve_res(res_id: int, db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403)
    res = db.query(models.Reservation).filter(models.Reservation.id == res_id).first()
    res.status = models.ReservationStatus.approved
    db.commit()
    db.refresh(res)
    return res

@router.get("/admin/billing-report")
def get_billing_report(
    month: Optional[int] = None, 
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim")

    today = date.today()
    target_month = int(month) if month else today.month
    target_year = int(year) if year else today.year

    month_pattern = f"{target_year}-{str(target_month).zfill(2)}-%"

    reservations = db.query(models.Reservation).filter(
        models.Reservation.status == models.ReservationStatus.approved,
        models.Reservation.date.like(month_pattern) 
    ).order_by(models.Reservation.date.desc()).all()

    report = []
    BASE_HOURLY_RATE = 1000
    HEATING_RATE = 300
    LIGHTING_RATE = 200

    for res in reservations:
        start = _minutes(res.start_time)
        end = _minutes(res.end_time)
        duration_hours = (end - start) / 60

        current_hourly_rate = BASE_HOURLY_RATE
        if res.heating_on: current_hourly_rate += HEATING_RATE
        if res.lighting_on: current_hourly_rate += LIGHTING_RATE

        total_price = duration_hours * current_hourly_rate

        player1 = "-"
        player2 = "-"

        if res.match_id and res.match:
            player1 = res.match.player1.full_name if res.match.player1 else "Bilinmeyen"
            player2 = res.match.player2.full_name if res.match.player2 else "-"
        else:
            player1 = res.user.full_name if res.user else "Bilinmeyen"

        # 🚀 ADMİN FİNANSAL GÜNCELLEME: Ücretlerin oyunculara bölüştürülmesi
        if player2 == "-":
            p1_price = total_price
            p2_price = 0
        else:
            p1_price = total_price / 2
            p2_price = total_price / 2

        report.append({
            "id": res.id,
            "player1": player1,
            "player2": player2,
            "duration": duration_hours,
            "heating": res.heating_on,
            "lighting": res.lighting_on,
            "hourly_rate": current_hourly_rate,
            "total_price": total_price,
            "p1_price": p1_price,   # Oyuncu 1'in ödemesi gereken net tutar
            "p2_price": p2_price,   # Oyuncu 2'nin ödemesi gereken net tutar
            "date": res.date,
            "time": f"{res.start_time} - {res.end_time}",
            "type": res.note
        })
    return report