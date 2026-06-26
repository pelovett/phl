from asyncio import sleep
from dataclasses import dataclass
from datetime import datetime

from phl.db import Database


@dataclass
class Schedule:
    every_hour: bool
    every_day_of_week: bool
    every_day: bool
    every_month: bool
    prompt: str = ""
    minute: int = -1
    hour: int = -1
    day_of_week: int = -1  # isoweekday
    day: int = -1
    month: int = -1

    def check(self, dt: datetime) -> bool:
        if dt.minute != self.minute:
            return False
        elif dt.hour != self.hour and not self.every_hour:
            return False
        elif dt.isoweekday() != self.day_of_week and not self.every_day_of_week:
            return False
        elif dt.day != self.day and not self.every_day:
            return False
        elif dt.month != self.month and not self.every_month:
            return False
        else:
            return True


async def create_schedule(db: Database, schedule: Schedule) -> None:
    await db.execute(
        """
        INSERT INTO schedules
            (minute, hour, day_of_week, day, month,
             every_hour, every_day_of_week, every_day, every_month, prompt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            schedule.minute,
            schedule.hour,
            schedule.day_of_week,
            schedule.day,
            schedule.month,
            int(schedule.every_hour),
            int(schedule.every_day_of_week),
            int(schedule.every_day),
            int(schedule.every_month),
            schedule.prompt,
        ),
    )
    await db.commit()


async def get_schedules(db: Database) -> list["Schedule"]:
    cursor = await db.execute("SELECT * FROM schedules")
    return [
        Schedule(
            minute=row["minute"],
            hour=row["hour"],
            day_of_week=row["day_of_week"],
            day=row["day"],
            month=row["month"],
            every_hour=bool(row["every_hour"]),
            every_day_of_week=bool(row["every_day_of_week"]),
            every_day=bool(row["every_day"]),
            every_month=bool(row["every_month"]),
            prompt=row["prompt"],
        )
        async for row in cursor
    ]


async def loop(db: Database):
    while True:
        now = datetime.now().replace(second=0, microsecond=0)
        print(f"Checking at time: {now}")
        for sched in await get_schedules(db):
            if sched.check(now):
                print(f"Cur time matches schedule: {sched}")
        await sleep(60 - datetime.now().second)
