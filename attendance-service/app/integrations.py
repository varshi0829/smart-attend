import httpx
import logging
from .config import FACE_SERVICE_URL, QR_SERVICE_URL, SERVICE_TIMEOUT, INTERNAL_TLS_VERIFY

logger = logging.getLogger("Integrations")

async def verify_face(roll_number: str, image_bytes: bytes, filename: str):
    """Call the Face Service API and preserve error details."""
    async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT, verify=INTERNAL_TLS_VERIFY) as client:
        try:
            files = {'image': (filename or 'image.jpg', image_bytes, 'image/jpeg')}
            data = {'roll_number': roll_number}
            
            logger.info(f"[INTEGRATION] Calling Face Service for {roll_number}")
            response = await client.post(f"{FACE_SERVICE_URL}/verify-face", data=data, files=files)
            
            raw_body = response.text
            logger.info(f"[INTEGRATION] Face Service raw response: {raw_body}")
            
            try:
                parsed = response.json()
                # Return parsed JSON and status code
                return parsed, response.status_code
            except Exception:
                logger.error(f"[INTEGRATION] Face service returned non-JSON: {raw_body[:200]}")
                return {"success": False, "message": "Face service returned invalid response format", "error_code": "INVALID_RESPONSE_FORMAT"}, 502
                
        except httpx.TimeoutException:
            logger.error("[INTEGRATION] Face service request timed out")
            return {"success": False, "message": "Face service request timed out", "error_code": "TIMEOUT"}, 504
        except Exception as e:
            logger.error(f"[INTEGRATION] Face service connection error: {repr(e)}")
            return {"success": False, "message": f"Face service connection error: {repr(e)}", "error_code": "CONNECTION_ERROR"}, 503

async def verify_qr(roll_number: str, qr_token: str):
    """Call the QR Service API and preserve error details."""
    # [PIPELINE] Debug logging for QR verification
    token_len = len(qr_token) if qr_token else 0
    logger.info(f"[PIPELINE] QR verify: roll={roll_number}, token_len={token_len}")
    
    async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT, verify=INTERNAL_TLS_VERIFY) as client:
        try:
            payload = {"roll_number": roll_number, "qr_token": qr_token}
            logger.info(f"[PIPELINE] Calling QR Service for {roll_number}")
            response = await client.post(f"{QR_SERVICE_URL}/session/verify-qr", json=payload)
            
            raw_body = response.text
            logger.info(f"[PIPELINE] QR Service status={response.status_code}, response={raw_body[:200]}")
            
            try:
                return response.json(), response.status_code
            except Exception:
                return {"success": False, "message": "QR service returned invalid response format", "error_code": "INVALID_RESPONSE_FORMAT"}, 502
                
        except httpx.TimeoutException:
            logger.error("[PIPELINE] QR service request timed out")
            return {"success": False, "message": "QR service request timed out", "error_code": "TIMEOUT"}, 504
        except Exception as e:
            logger.error(f"[PIPELINE] QR service error: {repr(e)}")
            return {"success": False, "message": f"QR service connection error: {repr(e)}", "error_code": "CONNECTION_ERROR"}, 503
