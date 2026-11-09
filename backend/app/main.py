import logging
import httpx
from fastapi import FastAPI,HTTPException,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .routers.auth import router as auth_router
from .routers.requisitions import router as requisitions_router
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
            async with httpx.AsyncClient(timeout=2) as client: await client.get(f'{settings.ollama_base_url}/api/tags')
        except Exception as exc:
            log.warning('Ollama unavailable; falling back to mock provider: %s',exc); settings.ai_mode='mock'
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(",")],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(auth_router,prefix="/api")
app.include_router(requisitions_router,prefix="/api")
@app.get('/api/meta')
def meta(): return provider_meta()
@app.get("/health")
def health(): return {"status":"ok"}

