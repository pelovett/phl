import aiosqlite
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:
    def __init__(self, path: str | Path = "phl.db"):
        self.path = Path(path)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> "Database":
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        return self

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def __aenter__(self) -> "Database":
        return await self.connect()

    async def __aexit__(self, *_):
        await self.close()

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        assert self._conn, "Not connected"
        return await self._conn.execute(sql, params)

    async def commit(self):
        assert self._conn, "Not connected"
        await self._conn.commit()

    async def migrate(self):
        assert self._conn, "Not connected"
        await self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _migrations (name TEXT PRIMARY KEY)"
        )
        await self._conn.commit()

        applied = {
            row[0]
            async for row in await self._conn.execute("SELECT name FROM _migrations")
        }

        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migration.name in applied:
                continue
            await self._conn.executescript(migration.read_text())
            await self._conn.execute(
                "INSERT INTO _migrations (name) VALUES (?)", (migration.name,)
            )
            await self._conn.commit()
