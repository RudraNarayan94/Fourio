import os
from typing import Tuple, Optional
from fastapi import HTTPException
from app.models.model import DBClient
from app.utils.utils import GetEnv
from .mongo_client import NewMongoClient
from .sqlite_client import NewSQLiteClient
from .hybrid_client import NewHybridClient
from app.utils.logger_setup import GetLogger

logger = GetLogger()

def NewDBClient() -> Tuple[Optional[DBClient], Optional[Exception]]:
    DBtype = GetEnv("DB_TYPE", "sqlite")

    if DBtype == "mongo" or DBtype == "hybrid":
        is_docker = os.path.exists("/.dockerenv")
        dbUsername = GetEnv("DB_USER")
        dbPassword = GetEnv("DB_PASS")
        dbName     = GetEnv("DB_NAME")
        dbHost     = GetEnv("DB_HOST")
        dbPort     = GetEnv("DB_PORT")
        mongoUri   = GetEnv("MONGO_URL")
        redisUri   = GetEnv("REDIS_URL")
        redisHost  = GetEnv("REDIS_HOST")
        redisPort  = GetEnv("REDIS_PORT", "6379")
        
        # Redis URI resolution
        if not redisUri:
            host = redisHost or ("redis" if is_docker else "localhost")
            redisUri = f"redis://{host}:{redisPort}/0"
        elif is_docker and ("localhost" in redisUri or "127.0.0.1" in redisUri):
            host = redisHost or "redis"
            redisUri = redisUri.replace("localhost", host).replace("127.0.0.1", host)
        elif not is_docker and ("//redis:" in redisUri):
            redisUri = redisUri.replace("//redis:", "//localhost:")

        # Mongo URI resolution
        if mongoUri:
            if is_docker and ("localhost" in mongoUri or "127.0.0.1" in mongoUri):
                host = dbHost or "mongo"
                dbUri = mongoUri.replace("localhost", host).replace("127.0.0.1", host)
            elif not is_docker and ("@mongo:" in mongoUri or "//mongo:" in mongoUri):
                dbUri = mongoUri.replace("@mongo:", "@localhost:").replace("//mongo:", "//localhost:")
            else:
                dbUri = mongoUri
        elif dbUsername and dbPassword:
            default_host = "mongo" if is_docker else "localhost"
            host = dbHost if (is_docker or dbHost not in ("mongo", "redis")) else default_host
            port = dbPort or "27017"
            name = dbName or "fourio"
            dbUri = f"mongodb://{dbUsername}:{dbPassword}@{host}:{port}/{name}?authSource=admin"
        else:
            default_host = "mongo" if is_docker else "localhost"
            dbUri = f"mongodb://{default_host}:27017"

        if DBtype == "mongo":
            return NewMongoClient(dbUri)

        if DBtype == "hybrid":
            return NewHybridClient(dbUri, redisUri)  

    elif DBtype == "sqlite":
        from pathlib import Path
        db_path = Path("db/db.sqlite3")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return NewSQLiteClient(str(db_path))

    return None, Exception(f"unsupported database type: {DBtype}")


def get_db_client() -> DBClient:
    db_client, err = NewDBClient()
    if err:
        logger.error(f"Error connecting to DB: {err}")
        raise HTTPException(status_code=500, detail="Database connection error")
    return db_client