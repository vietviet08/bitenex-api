import re
import secrets
import string
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def generate_uuid() -> str:
    """Generate a random UUID v4 string."""
    return str(uuid4())


def generate_short_id(length: int = 8) -> str:
    """
    Generate a short alphanumeric ID.
    Useful for order numbers, reference codes, etc.
    
    Args:
        length: Length of the ID (default 8)
        
    Returns:
        Alphanumeric string
    """
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_order_number() -> str:
    """
    Generate a unique order number.
    Format: ORD-YYYYMMDD-XXXXXX
    """
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = generate_short_id(6)
    return f"ORD-{date_part}-{random_part}"


def generate_transaction_id() -> str:
    """
    Generate a unique transaction ID.
    Format: TXN-XXXXXXXXXXXXXX
    """
    return f"TXN-{generate_short_id(14)}"


def utc_now() -> datetime:
    """Get current UTC timestamp with timezone info."""
    return datetime.now(timezone.utc)


def timestamp_to_iso(dt: datetime) -> str:
    """Convert datetime to ISO 8601 string."""
    return dt.isoformat()


def iso_to_timestamp(iso_string: str) -> datetime:
    """Parse ISO 8601 string to datetime."""
    return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))


def slugify(text: str) -> str:
    """
    Convert text to URL-friendly slug.
    
    Args:
        text: Text to slugify
        
    Returns:
        Lowercase slug with hyphens
    """
    # Convert to lowercase
    slug = text.lower()
    # Replace spaces with hyphens
    slug = re.sub(r"\s+", "-", slug)
    # Remove special characters
    slug = re.sub(r"[^\w\-]", "", slug)
    # Remove multiple consecutive hyphens
    slug = re.sub(r"\-+", "-", slug)
    # Strip hyphens from ends
    return slug.strip("-")


def mask_string(value: str, visible_chars: int = 4, mask_char: str = "*") -> str:
    """
    Mask a string, showing only last few characters.
    Useful for displaying sensitive data like card numbers.
    
    Args:
        value: String to mask
        visible_chars: Number of characters to show at the end
        mask_char: Character to use for masking
        
    Returns:
        Masked string (e.g., "****1234")
    """
    if len(value) <= visible_chars:
        return value
    
    mask_length = len(value) - visible_chars
    return mask_char * mask_length + value[-visible_chars:]


def normalize_phone(phone: str) -> str:
    """
    Normalize phone number by removing non-digit characters.
    
    Args:
        phone: Phone number string
        
    Returns:
        Digits only
    """
    return re.sub(r"\D", "", phone)


def remove_none_values(d: dict[str, Any]) -> dict[str, Any]:
    """
    Remove keys with None values from a dictionary.
    
    Args:
        d: Dictionary to clean
        
    Returns:
        Dictionary without None values
    """
    return {k: v for k, v in d.items() if v is not None}


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries.
    Override values take precedence.
    
    Args:
        base: Base dictionary
        override: Override dictionary
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def calculate_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Calculate distance between two points in kilometers.
    Uses Haversine formula.
    
    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates
        
    Returns:
        Distance in kilometers
    """
    import math
    
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def is_within_radius(
    center_lat: float,
    center_lon: float,
    point_lat: float,
    point_lon: float,
    radius_km: float,
) -> bool:
    """
    Check if a point is within a radius of a center point.
    
    Args:
        center_lat, center_lon: Center point coordinates
        point_lat, point_lon: Point to check
        radius_km: Radius in kilometers
        
    Returns:
        True if point is within radius
    """
    distance = calculate_distance(center_lat, center_lon, point_lat, point_lon)
    return distance <= radius_km
