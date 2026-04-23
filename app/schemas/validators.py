"""
Centralized validation functions for common security constraints.

These validators ensure consistent security policies across all schemas
and prevent security gaps due to inconsistent validation.
"""

import re
from pydantic import field_validator, ValidationInfo


def validate_password_strength(password: str) -> str:
    """
    Enforce consistent password requirements across the system.
    
    Requirements:
    - 8+ characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (!@#$%^&*()_+-=[]{}';:"\\|,.<>/?')
    
    Args:
        password: Password string to validate
    
    Returns:
        The validated password string
    
    Raises:
        ValueError: If password doesn't meet requirements
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit.")
    
    # Check for special characters
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};:'\"\\|,.<>\/?]", password):
        raise ValueError("Password must contain at least one special character (!@#$%^&*()_+-=[]{}';:\"\\|,.<>/?)")
    
    return password


def validate_name(name: str, field_name: str = "Name") -> str:
    """
    Validate person names - reject numeric characters and excessive punctuation.
    
    Args:
        name: Name string to validate
        field_name: Name of the field (for error messages)
    
    Returns:
        The validated name string
    
    Raises:
        ValueError: If name contains invalid characters
    """
    # Allow letters, spaces, hyphens, apostrophes, periods, parentheses, and commas
    if not re.match(r"^[a-zA-Z\s'\-\.\(\),]+$", name):
        raise ValueError(f"{field_name} can only contain letters, spaces, hyphens, apostrophes, periods, parentheses, and commas.")
    
    # Reject if mostly numbers
    digit_count = sum(c.isdigit() for c in name)
    if digit_count > len(name) * 0.3:  # More than 30% digits
        raise ValueError(f"{field_name} cannot contain mostly numbers.")
    
    return name
