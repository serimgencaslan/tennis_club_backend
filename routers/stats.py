from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from auth import get_current_user
import models
from collections import Counter
from datetime import datetime

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/me")
def get_personal_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Oyuncunun tüm tamamlanmış maçları
    matches = db.query(models.Match).filter(
        models.Match.status == models.MatchStatus.completed,
        (models.Match.player1_id == current_user.id) | (models.Match.player2_id == current_user.id)
    ).order_by(models.Match.played_at.asc()).all()

    total_matches = len(matches)
    won_matches = sum(1 for m in matches if m.winner_id == current_user.id)
    lost_matches = total_matches - won_matches
    win_rate = round((won_matches / total_matches * 100), 1) if total_matches > 0 else 0

    # Galibiyet Serisi (Streak) Hesaplama
    streak = 0
    # Maçları sondan başa doğru tarayarak güncel seriyi buluyoruz
    for m in reversed(matches):
        if m.winner_id == current_user.id:
            streak += 1
        else:
            break

    # En Çok Oynanan Rakip Bulma
    opponents = []
    court_success = {} # {court_name: [won, total]}
    monthly_performance = {} # {"Ocak": {"won": 0, "total": 0}}

    for m in matches:
        # Rakip tespiti
        opp_id = m.player2_id if m.player1_id == current_user.id else m.player1_id
        opp_user = m.player2 if m.player1_id == current_user.id else m.player1
        if opp_user:
            opponents.append(opp_user.full_name)

        # Kort Başarısı Analizi
        if m.court:
            c_name = m.court.name
            if c_name not in court_success:
                court_success[c_name] = [0, 0]
            court_success[c_name][1] += 1
            if m.winner_id == current_user.id:
                court_success[c_name][0] += 1

        # Aylık Gelişim Verisi (Son 6 Ay için formatlama)
        try:
            date_obj = datetime.strptime(m.played_at, "%Y-%m-%d")
            month_name = date_obj.strftime("%B") # Örn: May, June (Frontend'de Türkçeleştirilebilir)
        except:
            month_name = "Diğer"

        if month_name not in monthly_performance:
            monthly_performance[month_name] = {"won": 0, "total": 0}
        monthly_performance[month_name]["total"] += 1
        if m.winner_id == current_user.id:
            monthly_performance[month_name]["won"] += 1

    most_played_opponent = Counter(opponents).most_common(1)[0][0] if opponents else "Henüz Maç Yok"

    # En çok tercih edilen/başarılı olunan kort yapısı grafiğe uygun hale getiriliyor
    court_chart_data = [
        {"court": k, "Galibiyet": v[0], "Mağlubiyet": v[1] - v[0]} 
        for k, v in court_success.items()
    ]

    # Aylık form grafik datası
    monthly_chart_data = [
        {"month": k, "Galibiyet": v["won"], "Toplam": v["total"]} 
        for k, v in monthly_performance.items()
    ]

    return {
        "summary": {
            "total_matches": total_matches,
            "won": won_matches,
            "lost": lost_matches,
            "win_rate": win_rate,
            "streak": streak,
            "most_played_opponent": most_played_opponent
        },
        "monthly_chart": monthly_chart_data,
        "court_chart": court_chart_data
    }

@router.get("/admin/dashboard")
def get_admin_global_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Bu verilere sadece adminler erişebilir.")

    # 1. Genel Dağılımlar
    total_players = db.query(models.User).filter(models.User.role == models.RoleEnum.player).count()
    total_matches_played = db.query(models.Match).filter(models.Match.status == models.MatchStatus.completed).count()

    # Cinsiyet Dağılımı
    male_count = db.query(models.User).filter(models.User.gender == "male", models.User.role == models.RoleEnum.player).count()
    female_count = db.query(models.User).filter(models.User.gender == "female", models.User.role == models.RoleEnum.player).count()

    # 2. Kort Rezervasyon Yoğunluk Dağılımı (Pasta Grafik İçin)
    court_counts = db.query(
        models.Court.name, func.count(models.Reservation.id)
    ).join(models.Reservation, models.Court.id == models.Reservation.court_id).group_by(models.Court.name).all()

    court_distribution = [{"name": c[0], "value": c[1]} for c in court_counts]

    # 3. En Aktif Alt Ligler (Kategori Dağılımı)
    # Backend alt lig mantığı kullanıcıların category alanından ve cinsiyetinden süzülür
    active_leagues = db.query(
        models.User.gender, models.User.category, func.count(models.Match.id)
    ).join(models.Match, (models.User.id == models.Match.player1_id) | (models.User.id == models.Match.player2_id))\
     .filter(models.Match.status == models.MatchStatus.completed)\
     .group_by(models.User.gender, models.User.category).all()

    league_activity = {}
    for row in active_leagues:
        g_label = "Erkek" if row[0] == "male" else "Kadın"
        leag_name = f"{g_label} {row[1]}"
        # İki oyuncu da aynı ligde sayıldığı için ikiye bölerek normalize ediyoruz
        league_activity[leag_name] = league_activity.get(leag_name, 0) + (row[2] // 2)

    league_chart_data = [{"league": k, "Maç Sayısı": v if v > 0 else 1} for k, v in league_activity.items()]

    # 4. Saatlik Rezervasyon Yoğunluğu (Bar Grafik İçin)
    reservations = db.query(models.Reservation.start_time).all()
    hours = [r[0].split(":")[0] + ":00" for r in reservations if r[0]]
    hour_counts = Counter(hours)
    
    # Popüler saatleri sıralı diziye döküyoruz
    sorted_hours = sorted(hour_counts.items())
    hourly_chart_data = [{"hour": h, "Rezervasyon": c} for h, c in sorted_hours]

    return {
        "summary": {
            "total_players": total_players,
            "total_matches": total_matches_played,
            "male_players": male_count,
            "female_players": female_count
        },
        "court_chart": court_distribution,
        "league_chart": league_chart_data,
        "hourly_chart": hourly_chart_data
    }