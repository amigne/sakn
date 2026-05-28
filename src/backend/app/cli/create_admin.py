import asyncio
import sys

import click
from sqlalchemy import select

from app.constants.roles import ROLE_ADMINISTRATOR
from app.database import async_session_factory
from app.models import User
from app.models.base import new_uuid7, utcnow
from app.security.password import hash_password, validate_password_strength


@click.command("create-admin")
@click.option("--email", required=True, help="Admin email address")
@click.option("--password", required=True, help="Admin password")
@click.option("--first-name", default="Admin", help="First name")
@click.option("--last-name", default="User", help="Last name")
def create_admin(email: str, password: str, first_name: str, last_name: str):
    """Create an administrator account."""

    # Validate password strength
    valid, err_key = validate_password_strength(password)
    if not valid:
        click.echo(f"Error: password is too weak ({err_key}).", err=True)
        click.echo(
            "Password must be 8-128 characters with at least one uppercase letter, "
            "one lowercase letter, and one digit. It must not be a commonly-used password.",
            err=True,
        )
        sys.exit(1)

    async def _run():
        async with async_session_factory() as db:
            # Check if admin already exists
            result = await db.execute(
                select(User).where(User.email == email.strip().lower())
            )
            existing = result.scalar_one_or_none()
            if existing:
                click.echo(
                    f"User {email} already exists (role: {existing.role}, status: {existing.status}). "
                    f"Use --email with a different address."
                )
                sys.exit(1)

            # Create admin user (pre-verified, active)
            user = User(
                id=new_uuid7(),
                email=email.strip().lower(),
                password_hash=hash_password(password),
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                role=ROLE_ADMINISTRATOR,
                status="active",
                email_verified_at=utcnow(),
            )
            db.add(user)
            await db.commit()

            click.echo(f"Administrator {email} created ({user.id}).")

    asyncio.run(_run())
