from fastapi import FastAPI

app = FastAPI()

app.include_router(search_router, prefix="/search", tags=["Search"])

