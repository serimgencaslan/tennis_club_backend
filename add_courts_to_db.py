import os
import sys

# Projenizin içindeki models ve database dosyalarını rahatça bulabilmesi için 
# çalışma dizinini Python yoluna ekliyoruz (Render/Shell uyumluluğu için)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models
# 🚀 Kendi CourtStatus Enum yapınız hangi dosyadaysa oradan import edin 
# (Genelde models.py içindedir, eğer başka yerdeyse yolu güncelleyin)
from models import CourtStatus 

def seed_courts():
    # database.py dosyasındaki SessionLocal'ı kullanarak güvenli bir oturum açıyoruz
    db = SessionLocal()
    
    # Eklenecek kortların listesi
    # status alanına direkt string değil, modelin beklediği Enum objesini veriyoruz
    courts_to_add = [
        {"name": "Kort 1", "description": "Açık Kort", "status": CourtStatus.active},
        {"name": "Kort 2", "description": "Açık Kort", "status": CourtStatus.active},
        {"name": "Kort 3", "description": "Kapalı Kort", "status": CourtStatus.active},
    ]

    print("--- Kort ekleme işlemi başlatılıyor ---")
    
    for court_data in courts_to_add:
        # Mükerrer (aynı isimde) kayıt olmasın diye önce veritabanını kontrol ediyoruz
        existing_court = db.query(models.Court).filter(models.Court.name == court_data["name"]).first()
        
        if existing_court:
            print(f"[-] {court_data['name']} zaten veritabanında mevcut, atlanıyor.")
        else:
            # SQLAlchemy modeli üzerinden güvenli kayıt oluşturma
            new_court = models.Court(
                name=court_data["name"],
                description=court_data["description"],
                status=court_data["status"]
            )
            db.add(new_court)
            print(f"[+] {court_data['name']} başarıyla eklendi.")
            
    # Tüm değişiklikleri tek seferde veritabanına kaydedip kapatıyoruz
    db.commit()
    db.close()
    print("--- İşlem başarıyla tamamlandı! ---")

if __name__ == "__main__":
    seed_courts()