# This is a conceptual diff of what you need to change inside the generated env.py file.
# Add these imports at the top:
from app.config.settings import settings
from app.models.__init__ import Base

# Locate the target_metadata variable (usually set to None) and change it to:
target_metadata = Base.metadata

# Locate the run_migrations_offline function and update the url:
def run_migrations_offline() -> None:
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    # ... rest of the function remains the same