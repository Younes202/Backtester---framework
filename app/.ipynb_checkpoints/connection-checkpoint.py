from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from typing import TypeVar, List, Optional, Any
from sqlalchemy.orm import Query
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Database URL (set a default or override via an environment variable)
DATABASE_URL = os.getenv("DATABASE_URL")

# Base for  models
Base = declarative_base()
T = TypeVar('T', bound=Base)

# Create the SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Ensures the connection is alive before using
)

# SessionLocal for dependency injection in apps
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Generic Type for SQLAlchemy models

def get_db() -> Session:
    """
    Provides a database session.
    """
    db = SessionLocal()  # Create a new session
    return db  # Return the session directly


# Create all tables (only for development, avoid in production)
def initialize_database():
    """
    Creates tables for all models defined under Base.metadata.
    """
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")

class Database:
    def __init__(self, db_url: str = DATABASE_URL):
        """
        Initializes the Database class with a connection URL
        and sets up the engine and sessionmaker.
        """
        self.engine = create_engine(db_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_session(self) -> Session:
        """
        Creates and returns a database session.
        """
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def create(self, db: Session, model: T, **data: Any) -> T:
        """
        Create a new record in the database.
        """
        obj = model(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def read(self, db: Session, model: T, filters: Optional[dict] = None) -> List[T]:
        """
        Reads records from the database. Returns a list of records that match the filters.
        """
        query: Query = db.query(model)
        if filters:
            query = query.filter_by(**filters)
        return query.all()

    def update(self, db: Session, model: T, obj_id: int, **data: Any) -> Optional[T]:
        """
        Update an existing record in the database.
        """
        obj = db.query(model).filter(model.id == obj_id).first()
        if obj:
            for key, value in data.items():
                setattr(obj, key, value)
            db.commit()
            db.refresh(obj)
            return obj
        return None

    def delete(self, db: Session, model: T, obj_id: int) -> bool:
        """
        Deletes a record from the database.
        """
        obj = db.query(model).filter(model.id == obj_id).first()
        if obj:
            db.delete(obj)
            db.commit()
            return True
        return False



def test_connection():
   # Tests the database connection by running a simple query.
   # Returns True if the connection is successful, False otherwise.
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))  # Simple query to test connection
        print("Database connection successful!")
        return True
    except Exception as e:
        print(f"Database connection test failed: {e}")
        return False

# Main execution
if __name__ == "__main__":
    if test_connection():
        print("Database connection is successful!")
    else:
        print("Database connection failed.")