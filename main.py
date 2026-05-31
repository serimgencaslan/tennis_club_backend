from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import users, matches, reservations, stats   # ← reservations ekle

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tennis Club API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(matches.router)
app.include_router(reservations.router)   # ← ekle
app.include_router(stats.router)