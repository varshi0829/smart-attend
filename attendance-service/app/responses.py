from typing import Optional, Any
from fastapi.responses import JSONResponse

def standard_response(
    success: bool,
    message: str,
    data: Optional[Any] = None,
    error_code: Optional[str] = None,
    processing_time: Optional[float] = None,
    status_code: int = 200
):
    content = {
        "success": success,
        "message": message,
        "data": data,
        "error_code": error_code
    }
    if processing_time is not None:
        content["processing_time"] = processing_time
        
    return JSONResponse(status_code=status_code, content=content)
