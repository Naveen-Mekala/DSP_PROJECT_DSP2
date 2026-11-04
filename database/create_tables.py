from database.database import Base, engine
import database.models  # noqa: F401  (registers the tables on Base)

print("Creating database tables...")

Base.metadata.create_all(bind=engine)

print("✅ Database tables created successfully!")
