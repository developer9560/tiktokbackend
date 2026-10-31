from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import create_engine, text

from app import database
from app.config import Settings


def test_settings_ignore_dotenv_and_read_only_process_secrets(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "BRIGHTDATA_API_TOKEN=dotenv-token\nMYSQL_PASSWORD=dotenv-password\n"
        "BRIGHTDATA_BASE_URL=https://invalid.example\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BRIGHTDATA_API_TOKEN", raising=False)
    monkeypatch.delenv("MYSQL_PASSWORD", raising=False)

    assert Settings().brightdata_base_url == "https://api.brightdata.com"
    assert Settings().brightdata_keyword_dataset_id == "gd_lu702nij2f790tmv9h"
    assert Settings().request_timeout_seconds == 120.0
    assert Settings().mysql_host == "127.0.0.1"
    assert Settings().mysql_port == 3306
    assert Settings().mysql_user == "root"
    assert Settings().mysql_database == "tiktokdb"
    assert Settings().brightdata_api_token is None
    assert Settings().mysql_password is None
    assert database.resolve_database_url() is None

    monkeypatch.setenv("BRIGHTDATA_API_TOKEN", "process-token")
    monkeypatch.setenv("MYSQL_PASSWORD", "process-password")
    monkeypatch.setenv("BRIGHTDATA_BASE_URL", "https://process-env.example")
    config = Settings()
    assert config.brightdata_api_token == SecretStr("process-token")
    assert config.mysql_password == SecretStr("process-password")
    assert config.brightdata_base_url == "https://api.brightdata.com"
    database_url = database.resolve_database_url(config)
    assert database_url is not None
    assert database_url.drivername == "mysql+pymysql"
    assert database_url.username == "root"
    assert database_url.host == "127.0.0.1"
    assert database_url.database == "tiktokdb"
    assert database_url.password == "process-password"


def test_database_url_uses_secret_without_exposing_it_in_rendered_url() -> None:
    config = Settings(mysql_password="local-test-password")
    assert isinstance(config.mysql_password, SecretStr)
    database_url = database.resolve_database_url(config)
    assert database_url is not None
    assert "local-test-password" not in database_url.render_as_string(hide_password=True)


def test_database_readiness_requires_migrated_search_jobs_table(monkeypatch, caplog) -> None:
    test_engine = create_engine("sqlite://")
    monkeypatch.setattr(database, "engine", test_engine)

    assert database.check_database_connection() is False
    assert "table 'search_jobs' is missing" in caplog.text

    with test_engine.begin() as connection:
        connection.execute(text("CREATE TABLE search_jobs (id TEXT PRIMARY KEY)"))

    assert database.check_database_connection() is True
    test_engine.dispose()
