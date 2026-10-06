from contextlib import contextmanager


class BaseRepository:
    def __init__(self, session_factory):
        if session_factory is None:
            raise ValueError(
                "session_factory não pode ser None"
            )

        self.session_factory = session_factory

    @contextmanager
    def session(self):
        session = self.session_factory()

        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()