import logging
import httpx
from fastapi import FastAPI,HTTPException,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .routers.auth import router as auth_router
from .routers.requisitions import router as requisitions_router
from .routers.uploads import router as uploads_router
from .routers.applications import router as applications_router
from .ai.provider import provider_meta
from .workers.batch_processor import start_workers,stop_workers
app=FastAPI(title="ShortlistAI API")
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
@app.get('/api/meta')
def meta(): return provider_meta()
@app.get("/health")
@app.get("/api/health")
def health(): return {"status":"ok"}

