from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from .config import settings

def build_engine():
    if settings.data_source.lower() == "azure":
        required = [settings.azure_sql_server, settings.azure_sql_database,
                    settings.azure_sql_username, settings.azure_sql_password]
        if not all(required):
            raise RuntimeError("Configura server, database, username y password en backend/.env")
        url = URL.create(
            "mssql+pyodbc",
            username=settings.azure_sql_username,
            password=settings.azure_sql_password,
            host=settings.azure_sql_server,
            port=1433,
            database=settings.azure_sql_database,
            query={"driver": settings.azure_sql_driver, "Encrypt": "yes",
                   "TrustServerCertificate": "no", "Connection Timeout": "30"},
        )
        return create_engine(url, pool_pre_ping=True, pool_recycle=1800)
    return create_engine(f"sqlite:///{settings.demo_db_path}", connect_args={"check_same_thread": False})

engine = build_engine()
