import uvicorn
from app import CONFIG

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=str(CONFIG["server"]["host"]),
        port=int(CONFIG["server"]["port"]),
        log_level=str(CONFIG["logging"]["level"]).lower(),
    )
