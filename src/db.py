import psycopg
from pgvector.psycopg import register_vector

DB_DSN = "postgresql://civic:civic@localhost:5433/civic_radar"


def connect():
    """Open a connection and register PostgreSQL's vector type."""
    conn = psycopg.connect(DB_DSN)
    register_vector(conn)
    return conn


if __name__ == "__main__":
    with connect() as conn:
        row = conn.execute("SELECT version();").fetchone()
        print("Connected:", row[0])