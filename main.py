import os
import hmac
import hashlib
import json
from contextlib import asynccontextmanager
from urllib.parse import unquote
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import aiosqlite
import uvicorn
from dotenv import load_dotenv  # можна прибрати, але залишимо для сумісності

# Завантажуємо змінні оточення (не обов'язково, бо токен прямо в коді)
load_dotenv()
BOT_TOKEN = "8773076449:AAFAPKtwdD0USTWGLL2Wdz5NaxbEVIZDL6E"

DB_PATH = "casino.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 100.0,
                promo_used INTEGER DEFAULT 0
            )
        """)
        await db.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

from starlette.middleware.base import BaseHTTPMiddleware

class NgrokSkipWarningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

app.add_middleware(NgrokSkipWarningMiddleware)
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

class NgrokSkipWarningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

app.add_middleware(NgrokSkipWarningMiddleware)
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

@app.get("/")
async def root():
    with open("static/index.html", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

class SpinResult(BaseModel):
    win_amount: float
    new_balance: float

class RedeemRequest(BaseModel):
    code: str

def validate_init_data(init_data: str) -> dict:
    if not init_data:
        raise HTTPException(status_code=403, detail="No init data")
    vals = {k: unquote(v) for k, v in [s.split('=', 1) for s in init_data.split('&')]}
    data_check_string = '\n'.join(f"{k}={vals[k]}" for k in sorted(vals) if k != 'hash')
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if h != vals.get('hash'):
        raise HTTPException(status_code=403, detail="Invalid signature")
    return json.loads(vals.get('user', '{}'))

async def get_user_from_request(request: Request) -> int:
    init_data = request.headers.get('X-Telegram-Init-Data') or request.query_params.get('initData')
    if not init_data:
        raise HTTPException(status_code=403, detail="Auth required")
    user_data = validate_init_data(init_data)
    return int(user_data['id'])

@app.get("/api/balance")
async def get_balance(request: Request):
    user_id = await get_user_from_request(request)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()
            return {"balance": 100.0}
        return {"balance": row[0]}

PRIZE_WEIGHTS = [
    (0.5, 40),
    (2, 30),
    (10, 20),
    (20, 10),
    (70, 3),
    (300, 0.8),
    (1000, 0.05)
]

@app.get("/api/spin", response_model=SpinResult)
async def spin(request: Request):
    user_id = await get_user_from_request(request)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()
            balance = 100.0
        else:
            balance = row[0]

        if balance < 10:
            raise HTTPException(status_code=400, detail="Недостатньо коштів. Потрібно 10 ₴")

        import random
        total_weight = sum(w for _, w in PRIZE_WEIGHTS)
        r = random.uniform(0, total_weight)
        upto = 0
        win = 0
        for prize, weight in PRIZE_WEIGHTS:
            if upto + weight >= r:
                win = prize
                break
            upto += weight
        else:
            win = PRIZE_WEIGHTS[-1][0]

        new_balance = balance - 10 + win
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        await db.commit()
        return SpinResult(win_amount=win, new_balance=new_balance)

@app.post("/api/redeem")
async def redeem_code(request: Request, body: RedeemRequest):
    user_id = await get_user_from_request(request)
    code = body.code.strip().upper()
    if code != "AZART":
        raise HTTPException(status_code=400, detail="Невірний промокод")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT promo_used, balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()
            promo_used, balance = 0, 100.0
        else:
            promo_used, balance = row[0], row[1]

        if promo_used:
            raise HTTPException(status_code=400, detail="Промокод вже використано")

        new_balance = balance + 25.0
        await db.execute("UPDATE users SET balance = ?, promo_used = 1 WHERE user_id = ?", (new_balance, user_id))
        await db.commit()
        return {"new_balance": new_balance, "message": "Промокод AZART активовано! +25 ₴"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)