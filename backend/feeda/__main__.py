import uvicorn
from feeda.config import get_settings

def main():
    settings = get_settings()
    uvicorn.run("feeda.app:create_app", factory=True, host=settings.host, port=settings.port)

if __name__ == "__main__":
    main()
