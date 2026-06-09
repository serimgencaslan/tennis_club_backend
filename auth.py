from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas

SECRET_KEY = "BUNU_GIZLI_BIR_DEGERE_DEGISTIR"  # production'da env variable yap
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 gün

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# 🚀 GÜNCELLEME: APIRouter tanımı eklendi (Main dosyasında include_router ile bağlanmalı)
router = APIRouter(prefix="", tags=["Kimlik Doğrulama ve Yönetim"])

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def hash_password(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz kimlik bilgisi",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


# 🚀 GÜNCELLEME: FRONTEND'DEKİ 404 HATASINI ÇÖZEN YENİ ADMİN KULLANICI EKLEME ENDPOINT'İ
# routers/auth.py içindeki ilgili fonksiyon alanı güncellemesi

# routers/auth.py içindeki ilgili fonksiyon alanı

@router.post("/admin/users")
def admin_create_user(payload: schemas.UserCreateByAdmin, db: Session = Depends(get_db), 
                      current_user: models.User = Depends(get_current_user)):
    
    # 1. İstekte bulunan kişi gerçekten admin mi?
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlemi yapmak için yönetici yetkiniz bulunmamaktadır!"
        )

    # 2. Aynı e-posta adresiyle başka bir öğrenci var mı?
    email_exists = db.query(models.User).filter(models.User.email == payload.email).first()
    if email_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu e-posta adresi ile kayıtlı bir kullanıcı zaten mevcut!"
        )

    # 3. Şifreyi varsayılan olarak '123456' yapıp hash'liyoruz
    default_password = "123456"
    hashed_pwd = hash_password(default_password)

    # 4. Yeni kullanıcı kaydını oluştur
    db_user = models.User(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        category=payload.category,
        role="player",  # 🚀 DÜZELTME: 'user' yerine sisteminin tanıdığı 'player' Enum değeri atandı
        hashed_password=hashed_pwd,
        gender=payload.gender,  
        is_initial_password=True  
    )

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return {"status": "success", "message": "Öğrenci başarıyla oluşturuldu."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Veritabanına kaydedilirken bir hata oluştu: {str(e)}"
        )