from internal.service.app_config_service import AppConfigService


def test_invalid_model_config_fallback_isolated_between_calls():
    service = object.__new__(AppConfigService)
    first = service._process_and_validate_model_config(None)
    second = service._process_and_validate_model_config(None)
    expected_temperature = second["parameters"]["temperature"]

    first["parameters"]["temperature"] = 0.25

    assert second["parameters"]["temperature"] == expected_temperature
