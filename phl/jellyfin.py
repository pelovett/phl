from enum import Enum
from dataclasses import dataclass
import logging
import os
import sys
from typing import Optional


import httpx


class JellyfinItemType(Enum):
    Movie = "Movie"
    Show = "Series"


@dataclass
class JellyfinClient:
    url: str
    api_key: str
    user_id: Optional[str]


JELLYFIN_CLIENT: Optional[JellyfinClient] = None


def init_jellyfin() -> JellyfinClient:
    jellyfin_url = os.getenv("JELLYFIN_URL")
    if jellyfin_url is None:
        logging.error("Must set JELLYFIN_URL env var")
        sys.exit(1)

    jellyfin_api_key = os.getenv("JELLYFIN_API_KEY")
    if jellyfin_api_key is None:
        logging.error("Must set JELLYFIN_API_KEY env var")
        sys.exit(1)

    jellyfin_user_id = os.getenv("JELLYFIN_USER_ID")

    return JellyfinClient(
        url=jellyfin_url, api_key=jellyfin_api_key, user_id=jellyfin_user_id
    )


async def search_videos(query: str) -> Optional[list[dict[str, str]]]:
    global JELLYFIN_CLIENT
    if not JELLYFIN_CLIENT:
        JELLYFIN_CLIENT = init_jellyfin()

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url=JELLYFIN_CLIENT.url + "/Search/Hints",
            headers={
                "Authorization": f'MediaBrowser Token="{JELLYFIN_CLIENT.api_key}"'
            },
            params={"searchTerm": query, "mediaTypes": ["Video"]},
        )

    if response.status_code != 200:
        logging.error("Failed to search JellyfinAPI " + str(response.text))
        raise ValueError("Failed to query JellyfinAPI")

    return [
        {"Name": x["Name"], "Year": x["ProductionYear"], "ItemId": x["ItemId"]}
        for x in response.json()["SearchHints"]
    ]


async def get_all_items(
    item_type: Optional[JellyfinItemType] = None,
) -> Optional[dict]:
    global JELLYFIN_CLIENT
    if not JELLYFIN_CLIENT:
        JELLYFIN_CLIENT = init_jellyfin()

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url=JELLYFIN_CLIENT.url + "/Items",
            headers={
                "Authorization": f'MediaBrowser Token="{JELLYFIN_CLIENT.api_key}"'
            },
            params={
                "Recursive": True,
                "fields": "BasicSyncInfo",
                **(
                    {"userId": JELLYFIN_CLIENT.user_id}
                    if JELLYFIN_CLIENT.user_id
                    else {}
                ),
                **({"IncludeItemTypes": item_type.value} if item_type else {}),
            },
        )

    if response.status_code != 200:
        logging.error("Failed to retrieve items from JellyfinAPI " + str(response.text))
        raise ValueError("Failed to query JellyfinAPI")

    return response.json()
