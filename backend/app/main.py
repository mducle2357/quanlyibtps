import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm.exc import StaleDataError

from app.api.routes import auth, bond_fees, bonds, reference_rates, system, users
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.limiter import limiter

# Never log request bodies/headers at INFO+ (prompt §31: "Log lỗi không được ghi
# password/token") — the default uvicorn access log only logs method+path+status,
# which is safe; we do not add any body-logging middleware.
logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def handle_app_error(request: Request, exc: AppError):
    body = {"error": exc.error_code, "message": exc.message}
    if hasattr(exc, "current_version"):
        body["current_version"] = exc.current_version
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(StaleDataError)
def handle_stale_data(request: Request, exc: StaleDataError):
    return JSONResponse(
        status_code=409,
        content={
            "error": "conflict",
            "message": "Dữ liệu đã được thay đổi bởi người dùng khác. Vui lòng tải lại hoặc xem thay đổi trước khi ghi đè.",
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(reference_rates.router, prefix="/api")
app.include_router(bonds.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(bond_fees.router, prefix="/api")
