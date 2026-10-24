from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class AppError(Exception):
    """Base domain error — equivalent to AppError in Express templates."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def not_found(resource: str) -> AppError:
    return AppError(404, f"{resource} not found")


def bad_request(message: str) -> AppError:
    return AppError(400, message)


# ── FastAPI exception handlers ────────────────────────────────────────────────

async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    if not errors:
        return JSONResponse(status_code=422, content={"error": "Validation error"})
    first_error = errors[0]
    field = " → ".join(str(loc) for loc in first_error["loc"])
    return JSONResponse(
        status_code=422,
        content={"error": f"{field}: {first_error['msg']}"},
    )
