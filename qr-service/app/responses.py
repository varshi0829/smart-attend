from typing import Optional, Any
from fastapi.responses import JSONResponse

def standard_response(
    success: bool,
    message: str,
    data: Optional[Any] = None,
    error_code: Optional[str] = None,
    status_code: int = 200
):
    content = {
        "success": success,
        "message": message,
        "data": data,
        "error_code": error_code
    }
    return JSONResponse(status_code=status_code, content=content)
