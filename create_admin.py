from sqlalchemy.orm import Session
from database import SessionLocal
import models
from auth import hash_password
# Enumları modellerinden import etmelisin (Örn: models.RoleEnum)
from models import RoleEnum, GenderEnum 

def create_admin_account():
    db = SessionLocal()
    
    admin_email = "admin@tenis.com"
    admin_password = "admin_sifre_123"
    admin_name = "Sistem Admin"

    existing_user = db.query(models.User).filter(models.User.email == admin_email).first()
    
    if existing_user:
        print(f"--- {admin_email} yetkisi admin yapılıyor. ---")
        existing_user.role = RoleEnum.admin # String değil Enum objesi
        db.commit()
    else:
        print(f"--- Yeni admin hesabı oluşturuluyor. ---")
        new_admin = models.User(
            email=admin_email,
            full_name=admin_name,
            hashed_password=hash_password(admin_password),
            gender=GenderEnum.male, # Kendi Enum değerine göre değiştir (male/female/other)
            category="A",
            role=RoleEnum.admin, # RoleEnum.player yerine RoleEnum.admin
            is_active=True
        )
        # Not: User modelinde 'points' sütunu olmadığı için buraya eklemedik.
        db.add(new_admin)
        db.commit()
    
    db.close()
    print("İşlem başarıyla tamamlandı!")

if __name__ == "__main__":
    create_admin_account()