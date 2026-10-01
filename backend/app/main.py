from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import build_api_router
from app.core.config import get_settings
from app.core.product import Product
from app.core.product_config import product_config
from app.db.session import SessionLocal
from app.services.errors import DomainError

# Allowance on top of MAX_UPLOAD_BYTES for multipart framing and form fields.
_MULTIPART_OVERHEAD = 256 * 1024


def create_app(product: Product | None = None) -> FastAPI:
    """Build the application for one product (D-077).

    `product` defaults to the `PRODUCT` setting. Passing it explicitly lets one
    process build either application, which is how the tests exercise both.
    """
    settings = get_settings()
    config = product_config(product or settings.product)
    app = FastAPI(title=config.api_title, version="0.1.0", description=config.api_description)
    # Read by dependencies through the request, never from global settings, so
    # two applications in one process cannot see each other's product.
    app.state.product_config = config

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # bearer tokens, not cookies
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
    )

    @app.middleware("http")
    async def limits_and_headers(request: Request, call_next):
        # Reject oversized bodies before multipart parsing spools them to disk.
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > settings.max_upload_bytes + _MULTIPART_OVERHEAD:
            return JSONResponse({"detail": "Request body too large", "code": "file_too_large"}, status_code=413)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse({"detail": exc.message, "code": exc.code}, status_code=exc.status_code)

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok"}

    app.include_router(build_api_router(config.product))
    return app


app = create_app()
