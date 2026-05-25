#!/bin/sh
set -e

echo "SAKN backend startup..."

# Wait for PostgreSQL (poll until we can connect with python)
# NOTE: config.py MUST remain importable without database or network access.
# The inline python import below is the single source of truth for DATABASE_URL assembly.
echo "Validating configuration..."
python -c "from app.config import settings" || {
  echo "FATAL: Cannot load configuration. Check required environment variables (ENVIRONMENT, etc.)." >&2
  exit 1
}

echo "Waiting for PostgreSQL..."
until python -c "
import asyncio, asyncpg, sys
from app.config import settings
async def check():
    dsn = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://', 1)
    try:
        conn = await asyncio.wait_for(
            asyncpg.connect(dsn),
            timeout=5
        )
        await conn.close()
        return True
    except Exception:
        return False
asyncio.run(check()) or sys.exit(1)
"; do
  echo "PostgreSQL not ready — retrying in 2s..."
  sleep 2
done
echo "PostgreSQL is ready."

# Wait for Redis
echo "Waiting for Redis..."
# Parse REDIS_URL with Python urlparse (handles ACL format + special chars in password)
eval "$(python <<'PYEOF'
import os, urllib.parse, shlex
u = urllib.parse.urlparse(os.environ.get("REDIS_URL", "redis://redis:6379/0"))
print(f"REDIS_HOST={shlex.quote(u.hostname or 'redis')}")
print(f"REDIS_PORT={u.port or 6379}")
print(f"REDIS_PASS={shlex.quote(urllib.parse.unquote(u.password or ''))}")
print(f"REDIS_USER={shlex.quote(urllib.parse.unquote(u.username or ''))}")
PYEOF
)"

if [ -n "$REDIS_USER" ]; then
  REDIS_AUTH="--user $REDIS_USER -a $REDIS_PASS --no-auth-warning"
elif [ -n "$REDIS_PASS" ]; then
  REDIS_AUTH="-a $REDIS_PASS --no-auth-warning"
else
  REDIS_AUTH=""
fi
while ! redis-cli $REDIS_AUTH -h "${REDIS_HOST:-redis}" ping 2>/dev/null | grep -q PONG; do
  echo "Redis not ready — retrying in 2s..."
  sleep 2
done
echo "Redis is ready."

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the application
echo "Starting SAKN backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
