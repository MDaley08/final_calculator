from app.database import engine as default_engine
from app.models.user import Base

def init_db(engine=default_engine):
    Base.metadata.create_all(bind=engine)

def drop_db(engine=default_engine):
    Base.metadata.drop_all(bind=engine)

if __name__ == "__main__":
    init_db() # pragma: no cover