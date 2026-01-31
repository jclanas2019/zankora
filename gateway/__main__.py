from __future__ import annotations
import uvicorn
from gateway.config import load_settings
from gateway.server.app import create_app

def main():
    settings = load_settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())

if __name__ == "__main__":
    main()
