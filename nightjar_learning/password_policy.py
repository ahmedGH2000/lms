"""Nightjar's creation/change rules. Existing credentials remain valid at login."""

import unicodedata


def password_error(password, confirmation):
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        return "Choose a password between 8 and 128 characters."
    if not any("A" <= char <= "Z" for char in password):
        return "Include at least one uppercase letter (A–Z)."
    if not any(unicodedata.category(char)[0] in {"P", "S"} for char in password):
        return "Include at least one special character (for example ! @ #)."
    if password != confirmation:
        return "The passwords do not match."
    return None
