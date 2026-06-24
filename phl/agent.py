import logging

from langchain.tools import tool
from langchain_core.runnables import Runnable
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages.ai import AIMessage
from langchain_openrouter import ChatOpenRouter
from telegram import Message

from phl.jellyfin import search_videos, get_all_items, JellyfinItemType

# from langchain_core.globals import set_debug
# set_debug(True)

MAX_ITERATIONS = 10  # safety valve against infinite loop


@tool
async def search_jellyfin(query: str) -> list[dict[str, str]]:
    """
    Search the jellyfin server for movies and shows with
    title matching the provided query
    """
    if query == "":
        return []

    videos = await search_videos(query)
    if videos is None:
        logging.error("Failed to search videos")
        return []

    return videos


@tool
async def get_jellyfin_shows(**_) -> dict:
    """Get all shows on the jellyfin server"""
    result = await get_all_items(item_type=JellyfinItemType.Show)
    if not result:
        return {}
    return result


@tool
async def get_jellyfin_movies(**_) -> dict:
    """Get all movies on the jellyfin server"""
    result = await get_all_items(item_type=JellyfinItemType.Movie)
    if not result:
        return {}
    return result


tool_names_to_functions = {
    "search_jellyfin": search_jellyfin,
    "get_jellyfin_shows": get_jellyfin_shows,
    "get_jellyfin_movies": get_jellyfin_movies,
}


def get_model() -> Runnable[LanguageModelInput, AIMessage]:
    return ChatOpenRouter(
        model="deepseek/deepseek-v4-flash",
        temperature=0,
        max_tokens=1024,
        max_retries=2,
    ).bind_tools(list(tool_names_to_functions.values()))


async def process_message(model, telegram_message: Message):
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. Format your responses using Telegram HTML markup. "
                "Supported tags: <b>bold</b>, <i>italic</i>, <code>inline code</code>, "
                "<pre>code blocks</pre>, <u>underline</u>, <s>strikethrough</s>. "
                "Do not use Markdown. Do not use any HTML tags outside this set."
            ),
        },
        {
            "role": "user",
            "content": telegram_message.text,
        },
    ]
    ai_msg = await model.ainvoke(messages)
    await telegram_message.reply_text(ai_msg.text, parse_mode="HTML")
    messages.append(ai_msg)

    for _ in range(MAX_ITERATIONS):
        ai_msg = await model.ainvoke(messages)
        messages.append(ai_msg)

        if not ai_msg.tool_calls:
            # No more tools requested — this is the final answer
            await telegram_message.reply_text(ai_msg.text, parse_mode="HTML")
            return

        for tool_call in ai_msg.tool_calls:
            if tool_call["name"] not in tool_names_to_functions:
                raise ValueError("Unknown tool_call name: %s" % tool_call["name"])
            tool_result = await tool_names_to_functions[tool_call["name"]].ainvoke(
                tool_call
            )
            messages.append(tool_result)

    # Hit max_iterations without a final answer
    await telegram_message.reply_text(
        "Sorry, I got stuck thinking about that for too long.", parse_mode="HTML"
    )
