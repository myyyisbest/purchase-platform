"""
数据库连接配置
支持 PostgreSQL（本地开发）和 MySQL（CloudBase 部署）双模式
通过 DB_TYPE 环境变量切换，默认 mysql
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 数据库配置（支持环境变量配置；凭据不留可连接的硬编码默认值，统一走 .env）
DB_TYPE = os.getenv("DB_TYPE", "postgresql")  # mysql / postgresql
DB_HOST = os.getenv("DB_HOST", "localhost")
# 端口按数据库类型给安全默认（缺失时），postgresql=5432 / mysql=3306
DB_PORT = os.getenv("DB_PORT", "5432" if DB_TYPE == "postgresql" else "3306")
DB_NAME = os.getenv("DB_NAME", "purchase_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# 根据数据库类型构建连接URL
if DB_TYPE == "postgresql":
    SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    # MySQL：需要指定 utf8mb4 字符集
    SQLALCHEMY_DATABASE_URL = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?charset=utf8mb4"
    )

# 创建数据库引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_reset_on_return="rollback",  # 连接归还池时自动回滚，防止脏事务扩散
)

# 创建SessionLocal类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建Base类
Base = declarative_base()

# 依赖注入：获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
