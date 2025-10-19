from fastapi import FastAPI

app = FastAPI(
    title="Furio API",
    version="0.1.0",
    description="Audio fingerprinting & song recognition backend"
)

@app.get("/")
async def ping():
    return {"status": "Furio backend running"}
