import psycopg
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector


DB_DSN = "postgresql://civic:civic@localhost:5433/civic_radar"


def connect():
    """Open a connection and register PostgreSQL's vector type."""
    conn = psycopg.connect(
        DB_DSN,
        row_factory=dict_row,
    )
    register_vector(conn)
    return conn


if __name__ == "__main__":
    with connect() as conn:
        row = conn.execute(
            "SELECT version() AS version;"
        ).fetchone()

        print("Connected:", row["version"])
