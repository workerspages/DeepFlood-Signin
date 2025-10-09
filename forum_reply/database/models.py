"""
数据库模型定义
使用 SQLAlchemy Core 和 aiosqlite
"""

import sqlalchemy as sa
from sqlalchemy import (
    Table, Column, Integer, String, DateTime, Text, Boolean, MetaData
)
from datetime import datetime

# 使用 SQLAlchemy Core 定义表结构
metadata = MetaData()

# 已处理的帖子记录表
processed_posts = Table(
    'processed_posts',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('post_id', Integer, unique=True, nullable=False, index=True),
    Column('post_title', String(255), nullable=False),
    Column('processed_at', DateTime, default=datetime.utcnow, nullable=False),
    Column('status', String(50), default='pending', nullable=False),  # pending, replied, skipped, failed
    Column('error_message', Text, nullable=True)
)

# 回复记录表
reply_history = Table(
    'reply_history',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('post_id', Integer, sa.ForeignKey('processed_posts.post_id'), nullable=False, index=True),
    Column('reply_content', Text, nullable=False),
    Column('replied_at', DateTime, default=datetime.utcnow, nullable=False),
    Column('quality_score', sa.Float, nullable=True),
    Column('ai_provider', String(50), nullable=True),
    Column('ai_model', String(100), nullable=True),
    Column('is_fallback', Boolean, default=False, nullable=False)
)

# 运行日志表
run_logs = Table(
    'run_logs',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('run_started_at', DateTime, default=datetime.utcnow, nullable=False),
    Column('run_ended_at', DateTime, nullable=True),
    Column('status', String(50), nullable=False), # started, completed, failed
    Column('posts_found', Integer, default=0),
    Column('replies_sent', Integer, default=0),
    Column('errors_count', Integer, default=0),
    Column('log_message', Text, nullable=True)
)

def get_all_tables():
    """返回所有定义的表"""
    return [processed_posts, reply_history, run_logs]