"""Print the backend DATABASE_URL with a different database name (local use only)."""
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

env = dotenv_values(Path(__file__).resolve().parents[1] / "Marg-AppBackend" / ".env")
print(make_url(env["DATABASE_URL"]).set(database=sys.argv[1]).render_as_string(hide_password=False))
