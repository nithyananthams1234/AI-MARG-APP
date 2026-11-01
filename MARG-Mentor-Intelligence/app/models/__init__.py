"""Import all models so they register on ``Base.metadata``."""

from app.models import domain, engine  # noqa: F401
