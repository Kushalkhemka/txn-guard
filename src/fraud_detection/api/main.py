import uvicorn
from fastapi import FastAPI

from fraud_detection.api.routes import router
from fraud_detection.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.include_router(router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("fraud_detection.api.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
