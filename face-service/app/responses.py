from typing import Optional
from fastapi.responses import JSONResponse

def standard_response(
    success: bool,
    roll_number: str,
    message: str,
    confidence: float = 0.0,
    error_code: Optional[str] = None,
    processing_time: Optional[float] = None,
    status_code: int = 200
):
    content = {
        "success": success,
        "roll_number": roll_number,
        "confidence": confidence,
        "message": message,
        "error_code": error_code
    }
    if processing_time is not None:
        content["processing_time"] = processing_time
    
    return JSONResponse(status_code=status_code, content=content)
