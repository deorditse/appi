from enum import Enum

from fastapi import APIRouter, status, Query
from starlette.responses import JSONResponse

from src.domain.sites.armtek import search_armtek
from src.domain.sites.avito import search_avito
import asyncio

router = APIRouter()


class SearchSources(Enum):
    ARMTEK = "https://armtek.ru"
    AVITO = "https://www.avito.ru"


@router.get("/", status_code=status.HTTP_200_OK, description="Поиск по источникам", )
async def search(query: str = Query(...)) -> JSONResponse:
    try:

        tasks = _build_tasks(query)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        result = []
        for source_enum, data in zip(tasks.keys(), results):
            if isinstance(data, Exception):
                print("error ", str(data))
            else:
                result.append({"source": source_enum.value, "infrastructure": data})

        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

_TIMEOUT_SECONDS = 30  # установи нужное значение


def _build_tasks(query: str):
    return {
        SearchSources.ARMTEK: search_armtek(
            source=SearchSources.ARMTEK.value, article=query, user_agent=user_agent
        ),

        SearchSources.AVITO: search_avito(
            source=SearchSources.AVITO.value, article=query, user_agent=user_agent
        ),
    }
