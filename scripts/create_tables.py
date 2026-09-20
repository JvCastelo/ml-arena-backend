from app.db import engine
from app.models import Base


def main() -> None:
    Base.metadata.create_all(engine)
    print("Tables ensured:", ", ".join(Base.metadata.tables))


if __name__ == "__main__":
    main()
