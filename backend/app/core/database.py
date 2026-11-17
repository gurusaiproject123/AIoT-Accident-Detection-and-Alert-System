from supabase import Client, ClientOptions, create_client

from app.core.config import get_settings


def get_supabase_admin() -> Client:
    settings = get_settings()
    if settings.database_backend == "mysql":
        from app.localdb.storage import MySQLDatabase
        return MySQLDatabase()
    if settings.database_backend != "supabase":
        raise ValueError("Unsupported database backend")

    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key.get_secret_value(),
        options=ClientOptions(
            persist_session=False,
            auto_refresh_token=False,
        ),
    )
