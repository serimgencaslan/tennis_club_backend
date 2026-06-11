from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from auth import get_current_user
from typing import List

router = APIRouter(prefix="/admin-tournaments", tags=["Admin Turnuva Yönetimi"])

@router.post("/create")
def create_tournament(payload: schemas.TournamentCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Adminin tüm kuralları ve seçilen kategorileriyle birlikte yeni bir turnuva oluşturmasını sağlar"""
    
    # 1. Yetki Kontrolü
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlemi yapmak için yönetici yetkiniz bulunmamaktadır!"
        )

    # 2. Tarih Sıralama Kontrolü
    if payload.start_date > payload.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Başlangıç tarihi bitiş tarihinden sonra olamaz!"
        )

    # 3. Ana Turnuva Kaydını Oluştur
    db_tournament = models.Tournament(
        name=payload.name,
        tournament_type=payload.tournament_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="active"
    )
    db.add(db_tournament)
    db.flush()  # İlişkili alt kurallara tournament_id atayabilmek için geçici gömüyoruz

    # 4. Seçilen Kategorilerin Kurallarını Ekle
    for cat_rule in payload.categories:
        db_rule = models.TournamentRule(
            tournament_id=db_tournament.id,
            category_name=cat_rule.category_name,
            max_participants=cat_rule.max_participants,
            promoted_count=cat_rule.promoted_count
        )
        db.add(db_rule)

    try:
        db.commit()
        return {"status": "success", "message": "Turnuva ve kategori kuralları başarıyla oluşturuldu."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Turnuva kaydedilirken veritabanı hatası oluştu: {str(e)}"
        )

@router.get("/list")
def list_tournaments(db: Session = Depends(get_db)):
    """Sistemdeki tüm turnuvaları kuralları ve kategorileriyle birlikte listeler"""
    tournaments = db.query(models.Tournament).order_by(models.Tournament.id.desc()).all()
    
    result = []
    for t in tournaments:
        result.append({
            "id": t.id,
            "name": t.name,
            "tournament_type": "Lig Usulü" if t.tournament_type == "league" else "Grup Usulü",
            "start_date": t.start_date.isoformat(),
            "end_date": t.end_date.isoformat(),
            "status": t.status,
            "categories": [
                {
                    "category_name": r.category_name,
                    "max_participants": r.max_participants,
                    "promoted_count": r.promoted_count
                } for r in t.rules
            ]
        })
    return result

# routers/tournaments.py dosyasının en altına eklenecek alan:

@router.get("/detail/{tournament_id}")
def get_tournament_detail(tournament_id: int, db: Session = Depends(get_db)):
    """Turnuvanın türüne göre (Lig/Grup) puan durumu ve maç fikstürünü döner"""
    tournament = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Turnuva bulunamadı.")

    # Ortak Kategori Listesi
    categories = [r.category_name for r in tournament.rules]
    if not categories:
        categories = ["Erkek A", "Kadın A"]

    # 📊 LİG USULÜ İÇİN DUMMY VERİ MOTORU
    if tournament.tournament_type == "league":
        league_data = {}
        for cat in categories:
            league_data[cat] = {
                "standings": [
                    {"rank": 1, "player_name": "Ahmet Yılmaz", "played": 3, "won": 3, "lost": 0, "set_won": 6, "set_lost": 1, "set_avg": 5, "points": 6},
                    {"rank": 2, "player_name": "Caner Demir", "played": 3, "won": 2, "lost": 1, "set_won": 5, "set_lost": 2, "set_avg": 3, "points": 4},
                    {"rank": 3, "player_name": "Murat Kaya", "played": 3, "won": 1, "lost": 2, "set_won": 2, "set_lost": 4, "set_avg": -2, "points": 2},
                    {"rank": 4, "player_name": "Burak Şen", "played": 3, "won": 0, "lost": 3, "set_won": 0, "set_lost": 6, "set_avg": -6, "points": 0},
                ],
                "matches": [
                    {"id": 101, "player1": "Ahmet Yılmaz", "player2": "Caner Demir", "score": "2-1", "status": "completed", "date": "2026-06-10"},
                    {"id": 102, "player1": "Murat Kaya", "player2": "Burak Şen", "score": "2-0", "status": "completed", "date": "2026-06-11"},
                    {"id": 103, "player1": "Ahmet Yılmaz", "player2": "Burak Şen", "score": "2-0", "status": "completed", "date": "2026-06-12"},
                    {"id": 104, "player1": "Caner Demir", "player2": "Murat Kaya", "score": "2-0", "status": "completed", "date": "2026-06-13"},
                    {"id": 105, "player1": "Ahmet Yılmaz", "player2": "Murat Kaya", "score": "2-0", "status": "completed", "date": "2026-06-14"},
                    {"id": 106, "player1": "Caner Demir", "player2": "Burak Şen", "score": "Oynanmadı", "status": "pending", "date": "2026-06-15"},
                ]
            }
        return {
            "id": tournament.id,
            "name": tournament.name,
            "tournament_type": "league",
            "start_date": tournament.start_date.isoformat(),
            "end_date": tournament.end_date.isoformat(),
            "data": league_data
        }

    # 👥 GRUP USULÜ İÇİN DUMMY VERİ MOTORU
    else:
        group_data = {}
        for cat in categories:
            group_data[cat] = [
                {
                    "group_name": "A Grubu",
                    "standings": [
                        {"rank": 1, "player_name": "Mehmet Kurt", "played": 2, "won": 2, "lost": 0, "set_won": 4, "set_lost": 0, "set_avg": 4, "points": 4},
                        {"rank": 2, "player_name": "Selim Avcı", "played": 2, "won": 1, "lost": 1, "set_won": 2, "set_lost": 2, "set_avg": 0, "points": 2},
                        {"rank": 3, "player_name": "Emre Ünal", "played": 2, "won": 0, "lost": 2, "set_won": 0, "set_lost": 4, "set_avg": -4, "points": 0},
                    ],
                    "matches": [
                        {"id": 201, "player1": "Mehmet Kurt", "player2": "Selim Avcı", "score": "2-0", "status": "completed", "date": "2026-06-10"},
                        {"id": 202, "player1": "Selim Avcı", "player2": "Emre Ünal", "score": "2-0", "status": "completed", "date": "2026-06-11"},
                        {"id": 203, "player1": "Mehmet Kurt", "player2": "Emre Ünal", "score": "2-0", "status": "completed", "date": "2026-06-12"}
                    ]
                },
                {
                    "group_name": "B Grubu",
                    "standings": [
                        {"rank": 1, "player_name": "Ayşe Naz", "played": 2, "won": 2, "lost": 0, "set_won": 4, "set_lost": 1, "set_avg": 3, "points": 4},
                        {"rank": 2, "player_name": "Zeynep Bal", "played": 2, "won": 1, "lost": 1, "set_won": 3, "set_lost": 2, "set_avg": 1, "points": 2},
                        {"rank": 3, "player_name": "Fatma Esen", "played": 2, "won": 0, "lost": 2, "set_won": 0, "set_lost": 4, "set_avg": -4, "points": 0},
                    ],
                    "matches": [
                        {"id": 204, "player1": "Ayşe Naz", "player2": "Zeynep Bal", "score": "2-1", "status": "completed", "date": "2026-06-10"},
                        {"id": 205, "player1": "Zeynep Bal", "player2": "Fatma Esen", "score": "2-0", "status": "completed", "date": "2026-06-11"},
                        {"id": 206, "player1": "Ayşe Naz", "player2": "Fatma Esen", "score": "Oynanmadı", "status": "pending", "date": "2026-06-12"}
                    ]
                }
            ]
        return {
            "id": tournament.id,
            "name": tournament.name,
            "tournament_type": "group",
            "start_date": tournament.start_date.isoformat(),
            "end_date": tournament.end_date.isoformat(),
            "data": group_data
        }