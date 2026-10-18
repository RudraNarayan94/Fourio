import os
from dotenv import load_dotenv
from fastapi import FastAPI
from app.utils.file_io import CreateFolder
from app.utils.logger_setup import GetLogger
from app.api.router import router

logger = GetLogger()

def init_directories():
    for folder in ["tmp", os.getenv("SONGS_DIR", "songs"), "recordings", "db"]:
        try:
            CreateFolder(folder)
        except Exception as e:
            logger.error(f"Failed to create directory {folder}: {e}")

load_dotenv()
init_directories()


app = FastAPI(
  title="Fourio Backend",
  description="Backend service for audio fingerprinting",
  version="1.0.0"
)

app.include_router(router)



@app.get("/", include_in_schema=False)
def root():
    return {"message": "Backend is running. See /docs for API endpoints."}


if __name__ == "__main__":
    # run: uvicorn app.main:app --reload
    import uvicorn
    logger.info("starting server...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)