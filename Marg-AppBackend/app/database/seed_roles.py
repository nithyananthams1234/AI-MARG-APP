
import asyncio

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.identity import Role


DEFAULT_ROLES = [
    ("Mentor", "School mentor"),
    ("Supervisor", "Supervises mentors and school activities"),
    ("Administrator", "Platform administrator"),
]


async def seed_roles():
    async with AsyncSessionLocal() as session:
        for role_name, description in DEFAULT_ROLES:
            result = await session.execute(
                select(Role).where(Role.name == role_name)
            )

            if result.scalar_one_or_none() is None:
                session.add(
                    Role(
                        name=role_name,
                        description=description,
                    )
                )

        await session.commit()
        print("MARG roles seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed_roles())
