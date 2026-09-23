from fastapi import FastAPI;

app = FastAPI(title = "URL Shortener", version="1.0.0")

@app.get("/health")
def get_health():
    return {"status":"ok"}