from urllib.parse import urlencode

from fastapi.responses import RedirectResponse


def redirect_admin(
    tab: str,
    message: str | None = None,
    message_type: str = "info",
    path: str = "/admin",
    status_code: int = 303,
    **extra_query,
) -> RedirectResponse:
    query: dict[str, str] = {"tab": tab}
    if message:
        query["message"] = message.replace(" ", "+")
        query["message_type"] = message_type
    for k, v in extra_query.items():
        if v is not None and v != "":
            query[k] = str(v)
    url = f"{path}?{urlencode(query)}" if query else path
    return RedirectResponse(url=url, status_code=status_code)
