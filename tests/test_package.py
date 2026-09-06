import importlib


def test_package_is_importable() -> None:
    module = importlib.import_module("ai_service_desk")

    assert module.__name__ == "ai_service_desk"
