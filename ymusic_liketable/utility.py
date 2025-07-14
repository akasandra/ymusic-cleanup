from datetime import datetime, timezone

def iso_to_utc_timestamp(iso_str: str) -> int:
    # Parse ISO 8601 string (Python 3.8 requires replacing 'Z' with '+00:00' if present)
    dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    # Convert to UTC timezone if not already UTC
    dt_utc = dt.astimezone(timezone.utc)
    # Return Unix timestamp as int
    return int(dt_utc.timestamp())

def iso_to_utc_year(iso_str: str) -> int:
    # Parse ISO 8601 string (Python 3.8 requires replacing 'Z' with '+00:00' if present)
    dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    # Convert to UTC timezone if not already UTC
    dt_utc = dt.astimezone(timezone.utc)
    # Return year component
    return dt_utc.year

# google sheets/etc auto formatting bug: turns int fields into floats, parsed as X.0 instead of X
def strip_trailing_dot_zero(value) -> str:
    if value == None:
        return None
    s = str(value)
    if s.endswith('.0'):
        return s[:-2]  # remove the '.0' suffix
    return s

def value_to_bool(value) -> bool:
    # Normalize boolean value: openpyxl may read Excel TRUE/FALSE as str or bool
    if isinstance(value, str):
        value = value.strip().upper() == 'TRUE'
    return bool(value)