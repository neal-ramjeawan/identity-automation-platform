def validate_user_request(user):
    """
    Validate user request data.

    Args:
        user (dict): A dictionary containing user information

    Returns:
        bool: True if user is valid

    Raises:
        ValueError: If required fields are missing
    """
    required_fields = ["username", "firstname", "lastname", "department"]

    for field in required_fields:
        if field not in user:
            raise ValueError(f"Missing required field: {field}")

    return True
