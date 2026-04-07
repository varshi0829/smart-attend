import os
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Gateway")

app = FastAPI(title="SmartAttend API Gateway")

# Internal Service URLs
# Using 127.0.0.1 for internal calls
FACE_SERVICE = "https://127.0.0.1:5001"
QR_SERVICE = "https://127.0.0.1:5002"
ATTENDANCE_SERVICE = "https://127.0.0.1:5003"

# Root directory of the project
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# SSL verification for internal calls (can be disabled if using self-signed internal)
# Using same certs as other services usually means we need to verify against our own cert or skip
VERIFY_TLS = False 

async def proxy(target_url: str, request: Request):
    """Generic proxy handler"""
    client = httpx.AsyncClient(verify=VERIFY_TLS)
    
    # Path mapping: remove the gateway's prefix to reach the internal service path
    # Example: /api/face/health -> /health
    # Example: /api/attendance/session/123 -> /attendance/session/123 (if attendance service has /attendance prefix)
    
    path = request.url.path
    if path.startswith("/api/face"):
        url = f"{target_url}{path.replace('/api/face', '')}"
    elif path.startswith("/api/qr"):
        url = f"{target_url}{path.replace('/api/qr', '')}"
    elif path.startswith("/api/attendance"):
        url = f"{target_url}{path.replace('/api/attendance', '')}"
    else:
        url = f"{target_url}{path}"
        
    if request.query_params:
        url = f"{url}?{request.query_params}"

    # Forward headers, but remove 'host' to avoid issues
    headers = dict(request.headers)
    headers.pop("host", None)

    try:
        content = await request.body()
        response = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=content,
            timeout=60.0
        )
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
    except Exception as e:
        logger.error(f"Proxy error to {url}: {e}")
        return Response(content=f"Gateway Error: {str(e)}", status_code=502)
    finally:
        await client.aclose()

# API Proxy Routes
@app.api_route("/api/face/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def face_proxy(request: Request):
    return await proxy(FACE_SERVICE, request)

@app.api_route("/api/qr/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def qr_proxy(request: Request):
    return await proxy(QR_SERVICE, request)

@app.api_route("/api/attendance/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def attendance_proxy(request: Request):
    return await proxy(ATTENDANCE_SERVICE, request)

# Serve static frontend files
# Student app at / (default)
# Instructor app at /instructor

# We need to serve index.html for root routes explicitly sometimes
@app.get("/", response_class=HTMLResponse)
async def get_student_root():
    with open(os.path.join(ROOT_DIR, "frontend-student", "index.html"), "r") as f:
        return f.read()

@app.get("/student", response_class=HTMLResponse)
async def get_student_alt():
    with open(os.path.join(ROOT_DIR, "frontend-student", "index.html"), "r") as f:
        return f.read()

@app.get("/instructor", response_class=HTMLResponse)
async def get_instructor_root():
    with open(os.path.join(ROOT_DIR, "frontend-instructor", "index.html"), "r") as f:
        return f.read()

# Static files for assets if any (currently it's mostly single index.html files but good to have)
app.mount("/student-static", StaticFiles(directory=os.path.join(ROOT_DIR, "frontend-student")), name="student-static")
app.mount("/instructor-static", StaticFiles(directory=os.path.join(ROOT_DIR, "frontend-instructor")), name="instructor-static")

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Gateway is running"}
