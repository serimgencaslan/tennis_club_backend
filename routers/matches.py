from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
import models, schemas
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/matches", tags=["matches"])

LEVEL_MAP = {"A": 4, "B": 3, "C": 2, "D": 1}
BASE_WIN_POINT = 30
BASE_LOSS_POINT = 5

# ── YARDIMCI ZAMAN FONKSİYONLARI ──────────────────────────────

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

# ── İlan endpointleri ──────────────────────────────────────────

@router.post("/posts", response_model=schemas.MatchPostOut)
def create_post(post_data: schemas.MatchPostCreate, db: Session = Depends(get_db), 
                current_user: models.User = Depends(get_current_user)):
    
    # Rezervasyon çakışma kontrolü
    existing_reservations = db.query(models.Reservation).filter(
        models.Reservation.court_id == post_data.court_id,
        models.Reservation.date == post_data.date,
        models.Reservation.status.in_(["approved", "pending", "blocked"])
    ).all()

    for r in existing_reservations:
        if _overlaps(post_data.time_slot, post_data.end_time, r.start_time, r.end_time):
            raise HTTPException(
                status_code=400, 
                detail=f"Seçtiğiniz saatlerde ({r.start_time}-{r.end_time}) bu kort zaten rezerve edilmiş."
            )

    # 🚀 ADMİN ÖZEL DERS VEYA ARIZA / BAKIM AKIŞI (YENİ EKLENDİ)
    if post_data.match_type in ["ders", "arıza"]:
        if current_user.role != models.RoleEnum.admin:
            raise HTTPException(status_code=403, detail="Bu işlem için admin yetkisi gerekiyor.")

        # MatchPost kaydını üretiyoruz
        post_dict = post_data.model_dump()
        if isinstance(post_dict['category'], list):
            post_dict['category'] = ",".join(post_dict['category'])

        post_dict.pop('player1_id', None)
        post_dict.pop('player2_id', None)

        new_post = models.MatchPost(
            **post_dict,
            owner_id=current_user.id,
            status=models.MatchPostStatus.matched # Ders ve arızalar doğrudan 'matched/kilitli' başlar
        )
        if hasattr(new_post, 'reservation_type'):
            new_post.reservation_type = post_data.match_type

        db.add(new_post)
        db.flush()

        # Rezervasyon Durumunu Belirliyoruz
        final_status = models.ReservationStatus.approved
        if post_data.match_type == "arıza":
            final_status = models.ReservationStatus.blocked

        # Takvimde şık durması için etiket ekliyoruz
        type_label = post_data.match_type.upper()
        custom_note = post_data.note if post_data.note else ""
        final_note = f"[{type_label}] {custom_note}".strip()

        # 🚀 ARTIK TAKVİMDE GÖZÜKMESİ İÇİN RESERVATION KAYDINI OLUŞTURUYORUZ
        new_res = models.Reservation(
            court_id=post_data.court_id,
            user_id=current_user.id,
            date=post_data.date,
            start_time=post_data.time_slot,
            end_time=post_data.end_time,
            status=final_status,
            note=final_note
        )
        db.add(new_res)
        db.commit()
        db.refresh(new_post)
        return new_post

    # KİŞİSEL MAÇ / DOĞRUDAN KORT KİRALAMA AKIŞI
    if post_data.match_type == "kişisel":
        p1_id = post_data.player1_id if (current_user.role == models.RoleEnum.admin and post_data.player1_id) else current_user.id
        p2_id = post_data.player2_id if post_data.player2_id else None

        p1 = db.query(models.User).filter(models.User.id == p1_id).first()
        
        if not p1:
            raise HTTPException(status_code=404, detail="Ev sahibi oyuncu bulunamadı.")

        new_match = None
        reservation_note = ""

        if p2_id:
            p2 = db.query(models.User).filter(models.User.id == p2_id).first()
            if not p2:
                raise HTTPException(status_code=404, detail="Seçilen rakip oyuncu bulunamadı.")
            
            new_match = models.Match(
                player1_id=p1_id,
                player2_id=p2_id,
                category=p1.category,
                match_type="kişisel",
                played_at=post_data.date,
                start_time=post_data.time_slot,
                court_id=post_data.court_id,
                status=models.MatchStatus.scheduled
            )
            db.add(new_match)
            db.flush()
            reservation_note = f"[KİŞİSEL] {p1.full_name} vs {p2.full_name}"
        else:
            reservation_note = f"[KİŞİSEL] Bireysel Kullanım: {p1.full_name}"

        new_post = models.MatchPost(
            owner_id=p1_id,
            opponent_id=p2_id,
            date=post_data.date,
            time_slot=post_data.time_slot,
            end_time=post_data.end_time,
            category=p1.category,
            match_type="kişisel",
            note=post_data.note,
            court_id=post_data.court_id,
            status=models.MatchPostStatus.matched, 
            created_at=datetime.utcnow()
        )
        if hasattr(new_post, 'reservation_type'):
            new_post.reservation_type = "kişisel"
            
        db.add(new_post)
        db.flush() 

        new_res = models.Reservation(
            court_id=post_data.court_id,
            user_id=p1_id,
            date=post_data.date,
            start_time=post_data.time_slot,
            end_time=post_data.end_time,
            status=models.ReservationStatus.approved,
            note=f"{reservation_note} - {post_data.note if post_data.note else ''}".strip(" - "),
            match_id=new_match.id if new_match else None
        )
        db.add(new_res)
        db.commit()
        db.refresh(new_post)

        return new_post

    # BAHAR LİGİ MAÇI AKIŞI
    post_dict = post_data.model_dump()
    if isinstance(post_dict['category'], list):
        post_dict['category'] = ",".join(post_dict['category'])

    post_dict.pop('player1_id', None)
    post_dict.pop('player2_id', None)

    new_post = models.MatchPost(
        **post_dict,
        owner_id=current_user.id,
        status=models.MatchPostStatus.open
    )
    if hasattr(new_post, 'reservation_type'):
        new_post.reservation_type = post_data.match_type

    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post

@router.get("/posts", response_model=List[schemas.MatchPostOut])
def get_posts(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    all_posts = db.query(models.MatchPost).filter(
        (models.MatchPost.status == models.MatchPostStatus.open) | 
        (models.MatchPost.owner_id == current_user.id)
    ).all()
    
    if current_user.role == models.RoleEnum.admin:
        return db.query(models.MatchPost).filter(models.MatchPost.status != models.MatchPostStatus.cancelled).all()

    filtered_posts = []
    for post in all_posts:
        if post.owner_id == current_user.id:
            filtered_posts.append(post)
            continue
            
        if post.status == models.MatchPostStatus.open:
            allowed_categories = post.category.split(",") 
            if current_user.category in allowed_categories:
                filtered_posts.append(post)
                
    return filtered_posts

@router.post("/posts/{post_id}/respond", response_model=schemas.MatchPostOut)
def respond_to_post(post_id: int, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    post = db.query(models.MatchPost).filter(models.MatchPost.id == post_id).first()

    if not post:
        raise HTTPException(status_code=404, detail="İlan bulunamadı")
    if post.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Kendi ilanına katılamazsın")
    if post.status != models.MatchPostStatus.open:
        raise HTTPException(status_code=400, detail="Bu ilan artık açık değil")
    
    if current_user.category not in post.category.split(","):
        raise HTTPException(status_code=400, detail="Kategoriniz bu maç ilanı için uygun değil")

    if post.court_id:
        conflicts = db.query(models.Reservation).filter(
            models.Reservation.court_id == post.court_id,
            models.Reservation.date == post.date,
            models.Reservation.status.in_(["approved", "pending", "blocked"])
        ).all()
        
        for r in conflicts:
            if _overlaps(post.time_slot, post.end_time, r.start_time, r.end_time):
                raise HTTPException(
                    status_code=409, 
                    detail="Bu maç ilanına ait kort ve saatler maalesef başka bir rezervasyon tarafından doldurulmuş."
                )

    post.opponent_id = current_user.id
    post.status = models.MatchPostStatus.matched

    match = models.Match(
        player1_id=post.owner_id,
        player2_id=current_user.id,
        category=post.owner.category, 
        match_type=post.match_type,
        played_at=post.date,
        start_time=post.time_slot,
        court_id=post.court_id,
        status=models.MatchStatus.scheduled,
    )
    db.add(match)
    db.flush()  

    if post.court_id:
        reservation = models.Reservation(
            court_id=post.court_id,
            user_id=post.owner_id,
            date=post.date,
            start_time=post.time_slot,
            end_time=post.end_time,
            status=models.ReservationStatus.approved,
            note=f"[BAHAR LİGİ] {post.owner.full_name} vs {current_user.full_name}",
            match_id=match.id  
        )
        db.add(reservation)
    
    db.commit()
    db.refresh(post)
    return post

@router.delete("/posts/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    post = db.query(models.MatchPost).filter(models.MatchPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="İlan bulunamadı")
    if post.owner_id != current_user.id and current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Bu ilanı silemezsin")
    
    reservation = db.query(models.Reservation).filter(
        models.Reservation.court_id == post.court_id,
        models.Reservation.date == post.date,
        models.Reservation.start_time == post.time_slot
    ).first()
    if reservation:
        reservation.status = models.ReservationStatus.cancelled
        if reservation.match_id:
            linked_match = db.query(models.Match).filter(models.Match.id == reservation.match_id).first()
            if linked_match:
                db.delete(linked_match)

    post.status = models.MatchPostStatus.cancelled
    db.commit()
    return {"message": "İlan iptal edildi"}

# ── Maç endpointleri ──────────────────────────────────────────

@router.get("/my", response_model=List[schemas.MatchOut])
def get_my_matches(db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    return db.query(models.Match).filter(
        models.Match.match_type == "bahar ligi",
        ((models.Match.player1_id == current_user.id) | (models.Match.player2_id == current_user.id))
    ).order_by(models.Match.played_at.desc()).all()

@router.get("/all", response_model=List[schemas.MatchOut])
def get_all_matches_admin(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Bu verileri görme yetkiniz yok.")
    return db.query(models.Match).filter(models.Match.match_type == "bahar ligi").order_by(models.Match.played_at.desc()).all()

@router.post("/{match_id}/score", response_model=schemas.MatchOut)
def submit_score(match_id: int, score: schemas.ScoreSubmit, db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Maç bulunamadı")
        
    match.p1_set1 = score.p1_set1
    match.p2_set1 = score.p2_set1
    match.p1_set2 = score.p1_set2
    match.p2_set2 = score.p2_set2
    match.p1_set3 = score.p1_set3
    match.p2_set3 = score.p2_set3
    
    final_score_str = f"{score.p1_set1}-{score.p2_set1} {score.p1_set2}-{score.p2_set2}"
    if score.p1_set3 is not None:
        final_score_str += f" {score.p1_set3}-{score.p2_set3}"
    match.score = final_score_str

    p1_sets = (1 if score.p1_set1 > score.p2_set1 else 0) + (1 if score.p1_set2 > score.p2_set2 else 0)
    if score.p1_set3 is not None:
        p1_sets += (1 if score.p1_set3 > score.p2_set3 else 0)
    
    p2_sets = (3 if score.p1_set3 is not None else 2) - p1_sets
    
    winner = match.player1 if p1_sets > p2_sets else match.player2
    loser = match.player2 if p1_sets > p2_sets else match.player1
    match.winner_id = winner.id

    if match.match_type == "kişisel":
        match.p1_points = 0
        match.p2_points = 0
    else:
        w_val = LEVEL_MAP.get(winner.category, 2)
        l_val = LEVEL_MAP.get(loser.category, 2)
        
        final_win_point = BASE_WIN_POINT
        if w_val > l_val:
            final_win_point = int(BASE_WIN_POINT * 0.8)
        elif w_val < l_val:
            final_win_point = int(BASE_WIN_POINT * 1.2)

        if match.winner_id == match.player1_id:
            match.p1_points, match.p2_points = final_win_point, BASE_LOSS_POINT
        else:
            match.p1_points, match.p2_points = BASE_LOSS_POINT, final_win_point

    reservation = db.query(models.Reservation).filter(models.Reservation.match_id == match_id).first()
    
    if not reservation:
        reservation = db.query(models.Reservation).filter(
            models.Reservation.court_id == match.court_id,
            models.Reservation.date == match.played_at,
            models.Reservation.start_time == match.start_time
        ).first()

    if reservation:
        if hasattr(score, 'heating_on') and score.heating_on is not None:
            reservation.heating_on = bool(score.heating_on)
        if hasattr(score, 'lighting_on') and score.lighting_on is not None:
            reservation.lighting_on = bool(score.lighting_on)

    match.status = models.MatchStatus.completed
    db.commit()
    db.refresh(match)
    return match

@router.delete("/{match_id}")
def delete_match_admin(match_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim")
        
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Maç bulunamadı")
    
    reservation = db.query(models.Reservation).filter(models.Reservation.match_id == match_id).first()
    if reservation:
        db.delete(reservation)
        
    db.delete(match)
    db.commit()
    return {"message": "Maç ve ilgili rezervasyon silindi"}

@router.get("/leaderboard/{category}", response_model=List[schemas.LeaderboardEntry])
def get_leaderboard(category: str, gender: str = "male", db: Session = Depends(get_db)):
    users = db.query(models.User).filter(
        models.User.category == category,
        models.User.gender == gender
    ).all()
    
    result = []
    for u in users:
        matches = db.query(models.Match).filter(
            models.Match.status == models.MatchStatus.completed,
            models.Match.match_type == "bahar ligi", 
            (models.Match.player1_id == u.id) | (models.Match.player2_id == u.id)
        ).all()

        won = sum(1 for m in matches if m.winner_id == u.id)
        played = len(matches)
        lost = played - won
        points = sum(m.p1_points if m.player1_id == u.id else m.p2_points for m in matches)
        
        result.append(schemas.LeaderboardEntry(
            user=u, played=played, won=won, lost=lost,
            points=points, win_rate=round((won/played*100),1) if played > 0 else 0
        ))
    return sorted(result, key=lambda x: (-x.points, -(x.won - x.lost)))

@router.get("/users", response_model=List[schemas.UserOut])
def get_all_users_for_selection(gender: Optional[str] = None, category: Optional[str] = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    query = db.query(models.User)
    if gender:
        query = query.filter(models.User.gender == gender)
    if category:
        query = query.filter(models.User.category == category)
        
    return query.all()