from fastapi import FastAPI;
from app.api.routes.urls import router as url_router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title = "URL Shortener", version="1.0.0")

origins = [
    "http://localhost:5173",  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/health")
def get_health():
    return {"status":"ok"}

app.include_router(url_router)