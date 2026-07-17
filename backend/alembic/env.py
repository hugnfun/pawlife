"""Alembic 环境配置。

支持 SQLAlchemy 2.x 异步引擎 + asyncpg 驱动。
运行迁移时需要从项目根目录执行：
    cd /path/to/pawlife
    alembic -c backend/alembic.ini upgrade head
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool

from alembic import context

# 确保 backend 目录在 Python 路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.config import settings

# Alembic Config 对象
config = context.config

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置数据库 URL（优先使用环境变量，fallback 到 settings）
database_url = settings.database_url

# 将 asyncpg URL 转换为同步 psycopg2 URL 用于 Alembic 迁移
# Alembic 的迁移操作需要同步引擎
sync_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

config.set_main_option('sqlalchemy.url', sync_url)

# 导入所有模型，确保 Base.metadata 包含所有表定义
from models.base import Base

# 目标元数据
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """以 'offline' 模式运行迁移。

    只需要生成 SQL 脚本，不需要连接数据库。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """执行迁移。"""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """以 'online' 模式运行迁移。

    需要连接到实际数据库。
    """
    connectable = _get_sync_engine()

    with connectable.connect() as connection:
        do_run_migrations(connection)


def _get_sync_engine():
    """创建同步引擎用于 Alembic 迁移。"""
    from sqlalchemy import engine_from_config
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = sync_url
    return engine_from_config(
        configuration,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
