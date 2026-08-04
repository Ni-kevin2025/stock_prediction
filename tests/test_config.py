from stock_prediction.config import settings


def test_default_environment_is_development() -> None:
    assert settings.app_env == "development"
