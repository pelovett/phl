import asyncio
import logging
import sys
from typing import Any


from langchain.tools import tool
from langchain_openrouter import ChatOpenRouter

# from langchain_core.globals import set_debug


from phl.jellyfin import search_videos, get_all_items, JellyfinItemType

# set_debug(True)

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s : %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.INFO,
)


async def main():

    model = ChatOpenRouter(
        model="deepseek/deepseek-v4-flash",
        temperature=0,
        max_tokens=1024,
        max_retries=2,
    )

    @tool
    async def search_jellyfin(query: str) -> list[dict[str, str]]:
        """
        Search the jellyfin server for movies and shows with
        title matching the provided query
        """

        videos = await search_videos(query)
        if videos is None:
            logging.error("Failed to search videos")
            return []

        return videos

    @tool
    async def get_jellyfin_shows(**argv) -> dict:
        """Get all shows on the jellyfin server"""
        result = await get_all_items(item_type=JellyfinItemType.Show)
        if not result:
            return {}
        return result

    model_with_tools = model.bind_tools([search_jellyfin, get_jellyfin_shows])

    messages: Any = [
        {
            "role": "user",
            "content": " ".join(sys.argv[1:]),
        }
    ]
    ai_msg = model_with_tools.invoke(messages)
    messages.append(ai_msg)

    logging.info(ai_msg.text.strip())

    for tool_call in ai_msg.tool_calls:
        if tool_call["name"] == "search_jellyfin":
            tool_result = await search_jellyfin.ainvoke(tool_call)
        elif tool_call["name"] == "get_jellyfin_shows":
            tool_result = await get_jellyfin_shows.ainvoke(tool_call)
        else:
            raise ValueError("Unknown tool_call name: %s", tool_call["name"])
        messages.append(tool_result)

    final_response = model_with_tools.invoke(messages)
    logging.info(final_response.text)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
