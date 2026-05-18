#!/bin/sh
set -e

echo "SAKN backend startup..."

# Wait for PostgreSQL (poll until we can connect with python)
echo "Waiting for PostgreSQL..."
until python -c "
import asyncio, asyncpg, os
async def check():
    dsn = os.getenv('DATABASE_URL')
    if not dsn:
        print('DATABASE_URL is not set', file=sys.stderr)
        return False
    dsn = dsn.replace('postgresql+asyncpg://', 'postgresql://', 1)
    try:
        conn = await asyncio.wait_for(
            asyncpg.connect(dsn),
            timeout=5
        )
        await conn.close()
        return True
    except Exception:
        return False
asyncio.run(check()) or exit(1)
" 2>/dev/null; do
  echo "PostgreSQL not ready — retrying in 2s..."
  sleep 2
done
echo "PostgreSQL is ready."

# Wait for Redis
echo "Waiting for Redis..."
REDIS_HOST=$(echo "$REDIS_URL" | sed -n 's|.*@\?\([^:/]*\).*|\1|p')
while ! redis-cli -h "${REDIS_HOST:-redis}" ping 2>/dev/null | grep -q PONG; do
  echo "Redis not ready — retrying in 2s..."
  sleep 2
done
echo "Redis is ready."

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the application
echo "Starting SAKN backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
