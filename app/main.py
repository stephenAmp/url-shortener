from fastapi import FastAPI;
from app.api.routes.urls import router as url_router

app = FastAPI(title = "URL Shortener", version="1.0.0")

@app.get("/health")
def get_health():
    return {"status":"ok"}

app.include_router(url_router)