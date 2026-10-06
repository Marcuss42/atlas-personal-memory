from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from ..logger import debug_event
from .models import Base


def create_database(db_path):
    db_path = Path(db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        future=True,
        connect_args={"timeout": 30}
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys = ON")
        dbapi_connection.execute("PRAGMA busy_timeout = 30000")
        debug_event(
            "DB_CONNECT",
            database=str(db_path)
        )

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False
    )

    return engine, session_factory


def initialize_database(engine):
    debug_event(
        "DB_INIT_START",
        database=str(engine.url.database)
    )

    Base.metadata.create_all(engine)
    _ensure_relation_status(engine)
    _initialize_fts(engine)

    debug_event(
        "DB_INIT_COMPLETED",
        database=str(engine.url.database)
    )


def _ensure_relation_status(engine):
    with engine.begin() as conn:
        columns = conn.execute(
            text("PRAGMA table_info(relations)")
        ).mappings().all()

        column_names = {
            column["name"]
            for column in columns
        }

        if "status" not in column_names:
            conn.execute(
                text(
                    "ALTER TABLE relations "
                    "ADD COLUMN status VARCHAR NOT NULL DEFAULT 'current'"
                )
            )

            debug_event(
                "DB_RELATION_STATUS_ADDED"
            )

        conn.execute(
            text(
                "UPDATE relations "
                "SET status = 'current' "
                "WHERE status IS NULL"
            )
        )

        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_relations_status "
                "ON relations (status)"
            )
        )

        debug_event(
            "DB_RELATION_STATUS_READY"
        )


def _initialize_fts(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_index_fts
            USING fts5(
                search_text,
                content='memory_index',
                content_rowid='id',
                tokenize='unicode61 remove_diacritics 2'
            )
        """)

        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS memory_index_ai
            AFTER INSERT ON memory_index
            BEGIN
                INSERT INTO memory_index_fts(
                    rowid,
                    search_text
                )
                VALUES (
                    new.id,
                    new.search_text
                );
            END
        """)

        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS memory_index_ad
            AFTER DELETE ON memory_index
            BEGIN
                INSERT INTO memory_index_fts(
                    memory_index_fts,
                    rowid,
                    search_text
                )
                VALUES (
                    'delete',
                    old.id,
                    old.search_text
                );
            END
        """)

        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS memory_index_au
            AFTER UPDATE ON memory_index
            BEGIN
                INSERT INTO memory_index_fts(
                    memory_index_fts,
                    rowid,
                    search_text
                )
                VALUES (
                    'delete',
                    old.id,
                    old.search_text
                );

                INSERT INTO memory_index_fts(
                    rowid,
                    search_text
                )
                VALUES (
                    new.id,
                    new.search_text
                );
            END
        """)

    _ensure_fts_sync(engine)


def _ensure_fts_sync(engine):
    with engine.begin() as conn:
        memory_index_count = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM memory_index
            """)
        ).scalar_one()

        fts_count = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM memory_index_fts
            """)
        ).scalar_one()

        debug_event(
            "DB_FTS_STATUS",
            memory_index_count=memory_index_count,
            fts_count=fts_count
        )

        if memory_index_count != fts_count:
            debug_event(
                "DB_FTS_REBUILD",
                reason="index_count_mismatch",
                memory_index_count=memory_index_count,
                fts_count=fts_count
            )

            conn.exec_driver_sql("""
                INSERT INTO memory_index_fts(
                    memory_index_fts
                )
                VALUES ('rebuild')
            """)


def rebuild_memory_fts(engine):
    debug_event("DB_FTS_REBUILD_START")

    with engine.begin() as conn:
        conn.exec_driver_sql("""
            INSERT INTO memory_index_fts(
                memory_index_fts
            )
            VALUES ('rebuild')
        """)

    debug_event("DB_FTS_REBUILD_COMPLETED")