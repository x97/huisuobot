from urllib.parse import quote, unquote

def make_cb(prefix: str, action: str, *args) -> str:
    parts = [prefix, action] + [quote(str(a), safe='') for a in args]
    return ":".join(parts)

def parse_cb(callback_data: str):
    parts = callback_data.split(":")
    prefix = parts[0] if parts else ""
    action = parts[1] if len(parts) > 1 else ""
    args = [unquote(p) for p in parts[2:]] if len(parts) > 2 else []
    return prefix, action, args
