# -*- coding: utf-8 -*-
""" This module exports the database engine.

Notes:
     Using the scoped_session contextmanager is
     best practice to ensure the session gets closed
     and reduces noise in code by not having to manually
     commit or rollback the db if a exception occurs.
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def init(config):
    engine = create_engine(config.DATABASE_URL)
    # Session to be used throughout app.
    return sessionmaker(bind=engine)


@contextmanager
def scoped_session(session):
    session = session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
