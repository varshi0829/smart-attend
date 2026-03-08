# Start Services - Commands

## Prerequisites: Generate SSL Certificate
For camera access to work over LAN, you must use HTTPS. Run this in the root folder:
```bash
LAN_IP="192.168.19.90" # replace with your machine's LAN IP
openssl req -x509 -newkey rsa:4096 -nodes -days 365 \
  -keyout key.pem -out cert.pem \
  -subj "/CN=${LAN_IP}" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:${LAN_IP}"
```
*(Replace 192.168.19.90 with your actual LAN IP)*

---

## Terminal 1: Face Service (Port 5001)
```bash
cd face-service
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 5001 --ssl-keyfile ../key.pem --ssl-certfile ../cert.pem
```

## Terminal 2: QR Service (Port 5002)
```bash
cd qr-service
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 5002 --ssl-keyfile ../key.pem --ssl-certfile ../cert.pem
```

## Terminal 3: Attendance Orchestrator (Port 5003)
```bash
cd attendance-service
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 5003 --ssl-keyfile ../key.pem --ssl-certfile ../cert.pem
```

## Terminal 4: Student Frontend (Port 8001)
```bash
npx http-server ./frontend-student -a 0.0.0.0 -p 8001 --ssl --cert cert.pem --key key.pem
```

## Terminal 5: Instructor Frontend (Port 8002)
```bash
npx http-server ./frontend-instructor -a 0.0.0.0 -p 8002 --ssl --cert cert.pem --key key.pem
```

## Optional: Script-based Launch (Recommended)
```bash
cd /home/cse/smart-attend
SMARTATTEND_LAN_IP=192.168.19.90 ./start_services.sh
./start_frontends.sh
```

## URL Separation (Important)
- Backend internal service URLs (host-local): `attendance-service` calls `https://127.0.0.1:5001` and `https://127.0.0.1:5002`
- Browser-facing URLs (remote device): open frontends with `https://<LAN-IP>:8001` and `https://<LAN-IP>:8002`
- Frontend JS automatically targets `https://<browser-host>:5002` and `https://<browser-host>:5003`

---

## Important for Demo
When using self-signed certificates, your browser will show a warning. 
**You MUST visit and "Proceed" for EVERY port once:**
1. Open `https://<YOUR-IP>:8001` -> Advanced -> Proceed
2. Open `https://<YOUR-IP>:8002` -> Advanced -> Proceed
3. Open `https://<YOUR-IP>:5001/health` -> Advanced -> Proceed
4. Open `https://<YOUR-IP>:5002/health` -> Advanced -> Proceed
5. Open `https://<YOUR-IP>:5003/health` -> Advanced -> Proceed

---

## Demo Safety Option (localtunnel)
If HTTPS setup is too complex for the network, use localtunnel:
```bash
# In separate terminals
lt --port 8001
lt --port 8002
lt --port 5002
lt --port 5003
```
Update the URLs in the frontend HTML files to match the generated `.loca.lt` URLs.
