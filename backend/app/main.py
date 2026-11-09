import logging
import httpx
from fastapi import FastAPI,HTTPException,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from .config import settings
from .db import engine
from .routers.auth import router as auth_router
from .routers.requisitions import router as requisitions_router
from .routers.uploads import router as uploads_router
from .routers.applications import router as applications_router
from .routers.pipeline import router as pipeline_router
from .routers.portal import router as portal_router
from .routers.insights import router as insights_router
from .routers.compliance import router as compliance_router
from .ai.provider import provider_meta
from .workers.batch_processor import start_workers,stop_workers
app=FastAPI(title="ShortlistAI API",debug=False)
@app.on_event('startup')
async def start_batch_workers(): await start_workers()
@app.on_event('shutdown')
async def stop_batch_workers(): await stop_workers()
@app.exception_handler(HTTPException)
async def http_error(request:Request,exc:HTTPException):
    detail=exc.detail if isinstance(exc.detail,dict) else {'code':'http_error','message':str(exc.detail)}
    detail.setdefault('details',{})
    return JSONResponse(status_code=exc.status_code,content={'error':detail})
log=logging.getLogger(__name__)
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.env.casefold() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.on_event('startup')
async def provider_startup_check():
    if settings.ai_mode=='ollama':
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(f'{settings.ollama_base_url}/api/tags')
                response.raise_for_status()
                models = {item.get('name') for item in response.json().get('models', [])}
                if settings.ollama_model not in models and f'{settings.ollama_model}:latest' not in models:
                    raise RuntimeError(f'Ollama model {settings.ollama_model} is not installed')
        except Exception as exc:
            log.warning('Ollama unavailable; falling back to mock provider: %s',exc); settings.ai_mode='mock'
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(",")],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(auth_router,prefix="/api")
app.include_router(requisitions_router,prefix="/api")
app.include_router(uploads_router,prefix="/api")
app.include_router(applications_router,prefix="/api")
app.include_router(pipeline_router,prefix="/api")
app.include_router(portal_router,prefix="/api")
app.include_router(insights_router,prefix="/api")
app.include_router(compliance_router,prefix="/api")
@app.get('/api/meta')
def meta(): return provider_meta()
@app.get("/health")
@app.get("/api/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        log.error("Database health check failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail={"code": "database_unavailable", "message": "Database is unavailable."}) from exc
    return {"status":"ok", "database":"ok"}

