# fix_db.py
from database import SessionLocal
import models

def fix_database_roles_and_genders():
    db = SessionLocal()
    try:
        print("Veritabanı rolleri ve cinsiyetleri kontrol ediliyor...")
        
        # 1. Varsa eski 'Erkek'/'Kadın' verilerini düzelt
        db.query(models.User).filter(models.User.gender == "Erkek").update({models.User.gender: "male"}, synchronize_session=False)
        db.query(models.User).filter(models.User.gender == "Kadın").update({models.User.gender: "female"}, synchronize_session=False)
        
        # 2. 🚀 YENİ HATA İÇİN: Veritabanında kalmış 'user' rollerini 'player' olarak güncelle
        updated_roles_count = db.query(models.User).filter(models.User.role == "user").update(
            {models.User.role: "player"}, 
            synchronize_session=False
        )
        
        db.commit()
        print(f"Düzeltme tamamlandı!")
        print(f"-> {updated_roles_count} adet hatalı 'user' rolü 'player' olarak güncellendi.")
    except Exception as e:
        db.rollback()
        print(f"Hata oluştu: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_database_roles_and_genders()