import inspect
import logging
from dataclasses import dataclass
from typing import Annotated

from langchain.tools import tool
from langchain_core.runnables import Runnable
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages.ai import AIMessage
from langchain_core.tools import InjectedToolArg
from langchain_openrouter import ChatOpenRouter
from telegram import Message

from phl.cron import (
    Schedule,
    get_schedules as _get_schedules_from_db,
    create_schedule as _create_schedule_from_db,
)
from phl.db import Database
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


@tool
async def get_schedules(db: Annotated[Database, InjectedToolArg], **_) -> list[dict]:
    """Get all currently configured schedules"""
    schedules = await _get_schedules_from_db(db)
    return [vars(s) for s in schedules]


@tool
async def create_schedule(
    db: Annotated[Database, InjectedToolArg],
    prompt: str,
    minute: int,
    every_hour: bool = False,
    hour: int = -1,
    every_day_of_week: bool = False,
    day_of_week: int = -1,
    every_day: bool = False,
    day: int = -1,
    every_month: bool = False,
    month: int = -1,
) -> str:
    """Create a new schedule. Use every_* fields to indicate wildcards (like * in cron).
    Set the corresponding int field when every_* is False."""
    schedule = Schedule(
        prompt=prompt,
        minute=minute,
        every_hour=every_hour,
        hour=hour,
        every_day_of_week=every_day_of_week,
        day_of_week=day_of_week,
        every_day=every_day,
        day=day,
        every_month=every_month,
        month=month,
    )
    await _create_schedule_from_db(db, schedule)
    return "Schedule created."


_tools = {
    "search_jellyfin": search_jellyfin,
    "get_jellyfin_shows": get_jellyfin_shows,
    "get_jellyfin_movies": get_jellyfin_movies,
    "get_schedules": get_schedules,
    "create_schedule": create_schedule,
}


def _needs_db(tool_fn) -> bool:
    fn = getattr(tool_fn, "coroutine", None) or getattr(tool_fn, "func", None)
    return fn is not None and "db" in inspect.signature(fn).parameters


@dataclass
class Agent:
    model: Runnable[LanguageModelInput, AIMessage]
    db: Database

    async def process_message(self, telegram_message: Message) -> str:
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
        ai_msg = await self.model.ainvoke(messages)
        await telegram_message.reply_text(ai_msg.text, parse_mode="HTML")
        messages.append(ai_msg)

        for _ in range(MAX_ITERATIONS):
            ai_msg = await self.model.ainvoke(messages)
            messages.append(ai_msg)

            if not ai_msg.tool_calls:
                return ai_msg.text

            for tool_call in ai_msg.tool_calls:
                if tool_call["name"] not in _tools:
                    raise ValueError("Unknown tool_call name: %s" % tool_call["name"])
                tool_fn = _tools[tool_call["name"]]
                if _needs_db(tool_fn):
                    tool_call = {
                        **tool_call,
                        "args": {**tool_call["args"], "db": self.db},
                    }
                tool_result = await tool_fn.ainvoke(tool_call)
                messages.append(tool_result)

        return "Sorry, I got stuck thinking about that for too long."


def get_model(db: Database) -> Agent:
    model = ChatOpenRouter(
        model="deepseek/deepseek-v4-flash",
        temperature=0,
        max_tokens=1024,
        max_retries=2,
    ).bind_tools(list(_tools.values()))

    return Agent(model=model, db=db)
