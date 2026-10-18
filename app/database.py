import os

from psycopg_pool import ConnectionPool

pool = ConnectionPool(
    conninfo=os.environ["DATABASE_URL"],
    min_size=int(os.environ.get("DB_POOL_MIN_SIZE", "1")),
    max_size=int(os.environ.get("DB_POOL_MAX_SIZE", "10")),
    open=False,
)
