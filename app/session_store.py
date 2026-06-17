"""
会话管理 - 支持内存和 SQLite 存储。

提供统一的会话存储接口，支持：
- 内存存储（默认）
- SQLite 持久化存储（可选）
"""

import time
from abc import ABC, abstractmethod
from typing import Protocol

import aiosqlite

from app.logger import get_logger
from app.settings import settings

logger = get_logger(__name__)


class SessionStore(Protocol):
    """会话存储协议"""

    async def get(self, user: str) -> str | None:
        """获取会话 ID"""
        ...

    async def set(self, user: str, conversation_id: str) -> None:
        """设置会话 ID"""
        ...

    async def delete(self, user: str) -> bool:
        """删除会话"""
        ...

    async def list_all(self) -> list[tuple[str, str, float]]:
        """列出所有会话 (user, conversation_id, last_access)"""
        ...

    async def cleanup_expired(self) -> int:
        """清理过期会话，返回清理数量"""
        ...

    async def clear(self) -> int:
        """清空所有会话，返回清理数量"""
        ...

    async def close(self) -> None:
        """关闭存储"""
        ...

    # Response ID 映射（用于 /v1/responses API）
    async def get_response_conversation(self, response_id: str) -> str | None:
        """通过 response_id 获取 conversation_id"""
        ...

    async def set_response_conversation(self, response_id: str, conversation_id: str) -> None:
        """设置 response_id → conversation_id 映射"""
        ...

    async def clear_responses(self) -> int:
        """清空所有 response 映射，返回清理数量"""
        ...


class MemorySessionStore:
    """内存会话存储"""

    def __init__(self):
        self._store: dict[str, tuple[str, float]] = {}
        self._response_store: dict[str, str] = {}  # response_id → conversation_id

    async def get(self, user: str) -> str | None:
        """获取会话 ID"""
        if user in self._store:
            conversation_id, _ = self._store[user]
            self._store[user] = (conversation_id, time.time())
            return conversation_id
        return None

    async def set(self, user: str, conversation_id: str) -> None:
        """设置会话 ID"""
        self._store[user] = (conversation_id, time.time())

    async def delete(self, user: str) -> bool:
        """删除会话"""
        if user in self._store:
            del self._store[user]
            return True
        return False

    async def list_all(self) -> list[tuple[str, str, float]]:
        """列出所有会话"""
        return [(user, conv_id, last_time) for user, (conv_id, last_time) in self._store.items()]

    async def cleanup_expired(self) -> int:
        """清理过期会话"""
        if settings.session_expire_seconds <= 0:
            return 0

        now = time.time()
        expired_users = [
            user for user, (_, last_time) in self._store.items()
            if now - last_time > settings.session_expire_seconds
        ]

        for user in expired_users:
            del self._store[user]

        if expired_users:
            logger.info("清理过期会话", count=len(expired_users))

        return len(expired_users)

    async def clear(self) -> int:
        """清空所有会话"""
        count = len(self._store)
        self._store.clear()
        return count

    async def close(self) -> None:
        """关闭存储（内存模式无需操作）"""
        pass

    # Response ID 映射
    async def get_response_conversation(self, response_id: str) -> str | None:
        """通过 response_id 获取 conversation_id"""
        return self._response_store.get(response_id)

    async def set_response_conversation(self, response_id: str, conversation_id: str) -> None:
        """设置 response_id → conversation_id 映射"""
        self._response_store[response_id] = conversation_id

    async def clear_responses(self) -> int:
        """清空所有 response 映射"""
        count = len(self._response_store)
        self._response_store.clear()
        return count


class SQLiteSessionStore:
    """SQLite 会话存储"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def _ensure_db(self) -> aiosqlite.Connection:
        """确保数据库连接已建立"""
        if self._db is None:
            # 创建数据目录
            import os
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            self._db = await aiosqlite.connect(self.db_path)

            # 创建会话表
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    user TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    last_access REAL NOT NULL
                )
            """)
            await self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_access ON sessions(last_access)
            """)

            # 创建 response 映射表
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS response_mappings (
                    response_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

            await self._db.commit()
            logger.info("SQLite 会话存储已初始化", db_path=self.db_path)

        return self._db

    async def get(self, user: str) -> str | None:
        """获取会话 ID"""
        db = await self._ensure_db()
        cursor = await db.execute(
            "SELECT conversation_id FROM sessions WHERE user = ?",
            (user,)
        )
        row = await cursor.fetchone()

        if row:
            conversation_id = row[0]
            # 更新访问时间
            await db.execute(
                "UPDATE sessions SET last_access = ? WHERE user = ?",
                (time.time(), user)
            )
            await db.commit()
            return conversation_id

        return None

    async def set(self, user: str, conversation_id: str) -> None:
        """设置会话 ID"""
        db = await self._ensure_db()
        await db.execute(
            """
            INSERT INTO sessions (user, conversation_id, last_access)
            VALUES (?, ?, ?)
            ON CONFLICT(user) DO UPDATE SET
                conversation_id = excluded.conversation_id,
                last_access = excluded.last_access
            """,
            (user, conversation_id, time.time())
        )
        await db.commit()

    async def delete(self, user: str) -> bool:
        """删除会话"""
        db = await self._ensure_db()
        cursor = await db.execute("DELETE FROM sessions WHERE user = ?", (user,))
        await db.commit()
        return cursor.rowcount > 0

    async def list_all(self) -> list[tuple[str, str, float]]:
        """列出所有会话"""
        db = await self._ensure_db()
        cursor = await db.execute(
            "SELECT user, conversation_id, last_access FROM sessions"
        )
        return await cursor.fetchall()

    async def cleanup_expired(self) -> int:
        """清理过期会话"""
        if settings.session_expire_seconds <= 0:
            return 0

        db = await self._ensure_db()
        cutoff_time = time.time() - settings.session_expire_seconds
        cursor = await db.execute(
            "DELETE FROM sessions WHERE last_access < ?",
            (cutoff_time,)
        )
        await db.commit()

        if cursor.rowcount > 0:
            logger.info("清理过期会话", count=cursor.rowcount)

        return cursor.rowcount

    async def clear(self) -> int:
        """清空所有会话"""
        db = await self._ensure_db()
        cursor = await db.execute("SELECT COUNT(*) FROM sessions")
        row = await cursor.fetchone()
        count = row[0] if row else 0

        await db.execute("DELETE FROM sessions")
        await db.commit()
        return count

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._db is not None:
            await self._db.close()
            self._db = None
            logger.info("SQLite 连接已关闭")

    # Response ID 映射
    async def get_response_conversation(self, response_id: str) -> str | None:
        """通过 response_id 获取 conversation_id"""
        db = await self._ensure_db()
        cursor = await db.execute(
            "SELECT conversation_id FROM response_mappings WHERE response_id = ?",
            (response_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def set_response_conversation(self, response_id: str, conversation_id: str) -> None:
        """设置 response_id → conversation_id 映射"""
        db = await self._ensure_db()
        await db.execute(
            """
            INSERT INTO response_mappings (response_id, conversation_id, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(response_id) DO UPDATE SET
                conversation_id = excluded.conversation_id
            """,
            (response_id, conversation_id, time.time())
        )
        await db.commit()

    async def clear_responses(self) -> int:
        """清空所有 response 映射"""
        db = await self._ensure_db()
        cursor = await db.execute("SELECT COUNT(*) FROM response_mappings")
        row = await cursor.fetchone()
        count = row[0] if row else 0

        await db.execute("DELETE FROM response_mappings")
        await db.commit()
        return count


# 全局会话存储实例
_session_store: SessionStore | None = None


async def get_session_store() -> SessionStore:
    """获取会话存储实例（单例模式）"""
    global _session_store

    if _session_store is None:
        if settings.use_sqlite_session:
            _session_store = SQLiteSessionStore(settings.sqlite_db_path)
            logger.info("使用 SQLite 会话存储", db_path=settings.sqlite_db_path)
        else:
            _session_store = MemorySessionStore()
            logger.info("使用内存会话存储")

    return _session_store


async def close_session_store():
    """关闭会话存储"""
    global _session_store
    if _session_store is not None:
        await _session_store.close()
        _session_store = None
