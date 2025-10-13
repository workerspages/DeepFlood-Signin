"""
数据库操作模块
负责数据库的连接、初始化和异步CRUD操作
"""

import asyncio
import os
import aiosqlite
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable

from .models import metadata, processed_posts, reply_history, run_logs


class DatabaseManager:
    """异步数据库管理器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")

    async def initialize(self):
        """初始化数据库，创建所有表"""
        # 确保数据库目录存在
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            for table in metadata.sorted_tables:
                create_table_sql = str(CreateTable(table).compile(self.engine))
                # 添加 IF NOT EXISTS 关键字，以避免在表已存在时引发错误
                sql_if_not_exists = create_table_sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS")
                await db.execute(sql_if_not_exists)
            await db.commit()

    async def is_post_processed(self, post_id: int) -> bool:
        """检查帖子是否已被处理"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM processed_posts WHERE post_id = ?", (post_id,)
            )
            return await cursor.fetchone() is not None

    async def add_processed_post(self, post_id: int, post_title: str, status: str = 'pending'):
        """添加一个新的已处理帖子记录"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO processed_posts (post_id, post_title, status, processed_at) VALUES (?, ?, ?, ?)",
                (post_id, post_title, status, datetime.utcnow())
            )
            await db.commit()

    async def update_post_status(self, post_id: int, status: str, error_message: Optional[str] = None):
        """更新帖子处理状态"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE processed_posts SET status = ?, error_message = ? WHERE post_id = ?",
                (status, error_message, post_id)
            )
            await db.commit()

    async def add_reply_history(
        self,
        post_id: int,
        reply_content: str,
        quality_score: Optional[float] = None,
        ai_provider: Optional[str] = None,
        ai_model: Optional[str] = None,
        is_fallback: bool = False
    ):
        """记录一条回复历史"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO reply_history (post_id, reply_content, replied_at, quality_score, ai_provider, ai_model, is_fallback)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (post_id, reply_content, datetime.utcnow(), quality_score, ai_provider, ai_model, is_fallback)
            )
            await db.commit()

    async def count_replies_in_last_24_hours(self) -> int:
        """统计过去24小时内成功回复的数量"""
        async with aiosqlite.connect(self.db_path) as db:
            # aiosqlite 不直接支持 timedelta，需要手动计算时间戳
            # aiosqlite 不直接支持 timedelta，需要手动计算时间戳
            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
            cursor = await db.execute(
                "SELECT COUNT(*) FROM reply_history WHERE replied_at >= ?",
                (twenty_four_hours_ago,)
            )
            result = await cursor.fetchone()
            return result[0] if result else 0
 
    async def count_replies_today(self) -> int:
        """统计从今天零点（UTC）开始的成功回复数量"""
        async with aiosqlite.connect(self.db_path) as db:
            today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())
            cursor = await db.execute(
                "SELECT COUNT(*) FROM reply_history WHERE replied_at >= ?",
                (today_start,)
            )
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def start_run_log(self) -> int:
        """开始一次运行并记录日志，返回日志ID"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO run_logs (run_started_at, status) VALUES (?, ?)",
                (datetime.utcnow(), 'started')
            )
            await db.commit()
            return cursor.lastrowid

    async def end_run_log(
        self,
        log_id: int,
        status: str,
        posts_found: int = 0,
        replies_sent: int = 0,
        errors_count: int = 0,
        log_message: Optional[str] = None
    ):
        """结束一次运行日志记录"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE run_logs
                SET run_ended_at = ?, status = ?, posts_found = ?, replies_sent = ?, errors_count = ?, log_message = ?
                WHERE id = ?
                """,
                (datetime.utcnow(), status, posts_found, replies_sent, errors_count, log_message, log_id)
            )
            await db.commit()


async def main():
    """测试数据库模块功能"""
    print("--- 数据库模块测试 ---")
    db_manager = DatabaseManager("test_forum.db")

    print("1. 初始化数据库...")
    await db_manager.initialize()
    print("   数据库初始化完成。")

    test_post_id = 12345
    test_post_title = "这是一个测试帖子"

    print(f"\n2. 检查帖子 {test_post_id} 是否已处理...")
    processed = await db_manager.is_post_processed(test_post_id)
    print(f"   结果: {'是' if processed else '否'}")

    if not processed:
        print(f"\n3. 添加帖子 {test_post_id} 到处理列表...")
        await db_manager.add_processed_post(test_post_id, test_post_title)
        print("   添加完成。")

    print(f"\n4. 再次检查帖子 {test_post_id} 是否已处理...")
    processed = await db_manager.is_post_processed(test_post_id)
    print(f"   结果: {'是' if processed else '否'}")

    print("\n5. 更新帖子状态为 'replied'...")
    await db_manager.update_post_status(test_post_id, 'replied')
    print("   更新完成。")

    print("\n6. 添加一条回复历史...")
    await db_manager.add_reply_history(
        post_id=test_post_id,
        reply_content="测试回复内容",
        quality_score=0.85,
        ai_provider="test-api",
        ai_model="test-model-v1",
        is_fallback=False
    )
    print("   回复历史添加完成。")

    print("\n7. 记录一次运行日志...")
    log_id = await db_manager.start_run_log()
    print(f"   运行开始，日志ID: {log_id}")
    await asyncio.sleep(1)
    await db_manager.end_run_log(
        log_id=log_id,
        status='completed',
        posts_found=10,
        replies_sent=1,
        errors_count=0,
        log_message="测试运行成功"
    )
    print("   运行结束，日志已更新。")

    print("\n--- 测试完成 ---")
    # 清理测试数据库
    import os
    os.remove("test_forum.db")
    print("测试数据库已删除。")


if __name__ == "__main__":
    asyncio.run(main())