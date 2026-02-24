import secrets
import time

MINI_TOKEN_EXPIRY_SEC = 3600
_mini_tokens: dict[str, tuple[int, float]] = {}


def create_mini_token(telegram_id: int) -> str:
    token = secrets.token_urlsafe(32)
    _mini_tokens[token] = (telegram_id, time.time() + MINI_TOKEN_EXPIRY_SEC)
    return token


def get_telegram_id_by_mini_token(token: str) -> int | None:
    if not token:
        return None
    now = time.time()
    for k, (tid, exp) in list(_mini_tokens.items()):
        if exp < now:
            del _mini_tokens[k]
    data = _mini_tokens.get(token)
    if not data:
        return None
    tid, exp = data
    if exp < now:
        del _mini_tokens[token]
        return None
    return tid
