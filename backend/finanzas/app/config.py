from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Control de Compras API"
    data_source: str = "azure"
    cors_origins: str = "http://localhost:5173"
    demo_db_path: str = "./demo.db"
    azure_sql_server: str = ""
    azure_sql_database: str = ""
    azure_sql_username: str = ""
    azure_sql_password: str = ""
    azure_sql_driver: str = "ODBC Driver 18 for SQL Server"
    azure_invoices_view: str = "dbo.vw_FacturasNormalizadas"
    azure_receipts_view: str = "dbo.vw_RecepcionesNormalizadas"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
