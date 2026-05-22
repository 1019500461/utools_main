from typing import Any

from fastapi.responses import JSONResponse


def success(data: Any = None, msg: str = "OK", **kwargs: Any) -> JSONResponse:
    content = {"code": 200, "msg": msg, "data": data}
    content.update(kwargs)
    return JSONResponse(content=content, status_code=200)
