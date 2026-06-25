"""Helper script to check and seed the admin user.

Run with:
    docker compose exec api python -m app.scripts.check_admin
"""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.models import UserPreference
from app.models.user import User


async def check_and_create_admin():
    """Verify if an admin user exists, and create/update admin passwords."""
    async with async_session_factory() as session:
        # Check for admin@newsiq.io
        result = await session.execute(select(User).where(User.email == "admin@newsiq.io"))
        admin_io = result.scalar_one_or_none()

        if admin_io:
            admin_io.password_hash = hash_password("adminpassword123")
            admin_io.role = "admin"
            admin_io.email_verified = True
            print("❇️ Updated password for admin@newsiq.io to 'adminpassword123'")
        else:
            # Create admin@newsiq.io
            now = datetime.now(UTC).replace(tzinfo=None)
            admin_id = uuid.uuid4()
            admin_io = User(
                id=admin_id,
                email="admin@newsiq.io",
                name="System Admin",
                password_hash=hash_password("adminpassword123"),
                email_verified=True,
                role="admin",
                subscription_plan="enterprise",
                status="active",
                created_at=now,
                updated_at=now,
            )
            session.add(admin_io)
            session.add(
                UserPreference(
                    id=uuid.uuid4(),
                    user_id=admin_id,
                    preferred_summary_type="detailed",
                    theme="dark",
                    language="en",
                    created_at=now,
                    updated_at=now,
                )
            )
            print("❇️ Created admin@newsiq.io with password 'adminpassword123'")

        # Check for admin@newsiq.com (the UI placeholder email)
        result = await session.execute(select(User).where(User.email == "admin@newsiq.com"))
        admin_com = result.scalar_one_or_none()

        if admin_com:
            admin_com.password_hash = hash_password("adminpassword123")
            admin_com.role = "admin"
            admin_com.email_verified = True
            print(
                "❇️ Updated/Promoted admin@newsiq.com to admin role with password 'adminpassword123'"
            )
        else:
            # Create admin@newsiq.com
            now = datetime.now(UTC).replace(tzinfo=None)
            admin_id = uuid.uuid4()
            admin_com = User(
                id=admin_id,
                email="admin@newsiq.com",
                name="NewsIQ Admin",
                password_hash=hash_password("adminpassword123"),
                email_verified=True,
                role="admin",
                subscription_plan="enterprise",
                status="active",
                created_at=now,
                updated_at=now,
            )
            session.add(admin_com)
            session.add(
                UserPreference(
                    id=uuid.uuid4(),
                    user_id=admin_id,
                    preferred_summary_type="detailed",
                    theme="dark",
                    language="en",
                    created_at=now,
                    updated_at=now,
                )
            )
            print("❇️ Created admin@newsiq.com with password 'adminpassword123'")

        await session.commit()
        print("\n🎉 Seeding and verification of Admin credentials complete!")
        print("----------------------------------------------------------")
        print("You can use either of the following credentials to login:")
        print("1. Email: admin@newsiq.com   | Password: adminpassword123")
        print("2. Email: admin@newsiq.io    | Password: adminpassword123")


if __name__ == "__main__":
    asyncio.run(check_and_create_admin())
