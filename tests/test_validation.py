import pytest
from identity_automation_platform.validation.validator import (
    validate_user_request,
)


def test_valid_user():
    user = {
        "username": "jdoe",
        "firstname": "John",
        "lastname": "Doe",
        "department": "Finance",
    }

    assert validate_user_request(user) is True


def test_missing_fields():
    user = {"username": "jdoe"}

    with pytest.raises(ValueError):
        validate_user_request(user)
