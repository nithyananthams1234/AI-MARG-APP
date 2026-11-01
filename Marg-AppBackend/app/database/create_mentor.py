
import asyncio
from getpass import getpass

from sqlalchemy import select

from app.auth.hashing import hash_password
from app.database.session import AsyncSessionLocal
from app.models.identity import User, UserRole, Role


async def create_mentor():
    print("\n--- MARG Mentor Account Setup ---")

    full_name = input("Mentor name: ").strip()
    email = input("Mentor email: ").strip().lower()
    password = getpass("Create password: ")
    confirm_password = getpass("Confirm password: ")

    if not full_name or not email:
        print("Name and email are required.")
        return

    if len(password) < 12 or len(password) > 128:
        print("Password must contain between 12 and 128 characters.")
        return

    if password != confirm_password:
        print("Passwords do not match.")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )

        if result.scalar_one_or_none():
            print("A user with this email already exists.")
            return

        result = await session.execute(
            select(Role).where(Role.name == "Mentor")
        )

        mentor_role = result.scalar_one_or_none()

        if mentor_role is None:
            print("Mentor role not found. Run seed_roles first.")
            return

        mentor = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            is_active=True,
        )

        session.add(mentor)
        await session.flush()

        session.add(
            UserRole(
                user_id=mentor.id,
                role_id=mentor_role.id,
            )
        )

        await session.commit()

        print("\nMentor account created successfully.")
        print("Email:", email)
        print("Role: Mentor")


if __name__ == "__main__":
    asyncio.run(create_mentor())
