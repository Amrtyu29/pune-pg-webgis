"""Tiny helper shared by the notebooks: read the database settings from the repo's .env
(never committed) and hand back a SQLAlchemy engine.

Usage inside a notebook:
    from dbconf import engine_from_env
    engine = engine_from_env()
"""
from pathlib import Path
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]


def read_env(path: Path = ROOT / ".env") -> dict:
    """Parse KEY=VALUE lines; ignores blanks and # comments. No library needed."""
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def database_url(env: dict | None = None) -> str:
    """URL for the host side: the Compose file maps container port 5432 to POSTGRES_PORT on localhost."""
    env = env or read_env()
    return (f"postgresql+psycopg://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
            f"@localhost:{env.get('POSTGRES_PORT', '5434')}/{env['POSTGRES_DB']}")


def engine_from_env():
    return create_engine(database_url(), future=True)
