from app.models import Base

from app.db import engine


def main() -> None:
    Base.metadata.create_all(engine)
    print("Tables ensured:", ", ".join(Base.metadata.tables))


if __name__ == "__main__":
    main()
