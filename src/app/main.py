from fastapi import FastAPI
from src.domain.search import  router as search_router

app = FastAPI()

app.include_router(search_router, prefix="/search", tags=["Search"])

