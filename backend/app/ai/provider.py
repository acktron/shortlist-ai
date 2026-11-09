import logging
from .mock import MockProvider
from .ollama import OllamaProvider
try: from .gemini import GeminiProvider
except ImportError: GeminiProvider=None
from ..config import settings
log=logging.getLogger(__name__)
def get_provider():
    if settings.ai_mode=='ollama': return OllamaProvider()
    if settings.ai_mode=='gemini' and GeminiProvider: return GeminiProvider()
    return MockProvider()
def provider_meta():
    p=get_provider(); return {'ai_mode':settings.ai_mode,'model':getattr(p,'model','mock')}
