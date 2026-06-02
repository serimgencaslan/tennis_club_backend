from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=schemas.UserOut)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı")

    hashed_pw = auth.hash_password(user.password)
    print("categry: ", user.category)
    new_user = models.User(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_pw,
        gender=user.gender,
        category=user.category,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı")

    token = auth.create_access_token(data={"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "is_initial_password": user.is_initial_password  # 🚀 Artık frontend'e ulaşacak!
    }


@router.post("/change-initial-password")
def change_initial_password(
    data: schemas.ChangePasswordSchema, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    if not current_user.is_initial_password:
        raise HTTPException(status_code=400, detail="Şifreniz zaten güncellenmiş.")
        
    # Yeni şifreyi hashleyip kaydediyoruz
    current_user.hashed_password = auth.hash_password(data.new_password)
    # 🚀 KRİTİK KISIM: Artık ilk şifrede değil, zorunluluğu kaldırıyoruz.
    current_user.is_initial_password = False 
    
    db.commit()
    return {"message": "Şifreniz başarıyla güncellendi. Artık sistemi kullanabilirsiniz."}

@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user