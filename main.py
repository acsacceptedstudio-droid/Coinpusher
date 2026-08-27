import firebase_admin
from firebase_admin import credentials, auth
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import pymysql
import redis
from contextlib import asynccontextmanager

# 1. MySQL 與 Redis 設定
MYSQL_HOST = "localhost"
MYSQL_USER = "root"         # 你的 MySQL 帳號
MYSQL_PASSWORD = "super1019" # 你的 MySQL 密碼
MYSQL_DB = "game_db"

redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# 2. 初始化 Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate(r"C:\Users\User\OneDrive\Desktop\AcceptedStudio\LoginServer\Firebase_service.json")
    firebase_admin.initialize_app(cred)

# 3. 定義 Lifespan 生命週期（自動建立資料庫與 Table）
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 建立 Database
    conn = pymysql.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD)
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB};")
    conn.close()

    # 建立 Table
    conn = pymysql.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DB)
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                firebase_uid VARCHAR(128) PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                username VARCHAR(50) DEFAULT 'NewPlayer',
                level INT DEFAULT 1,
                gold INT DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()
    conn.close()
    
    yield

# 4. 建立唯一的 FastAPI 實例並帶入 lifespan
app = FastAPI(lifespan=lifespan)

# 5. 加入 CORS 中間件（必須在 app 建立後設定，且全域只設定一次）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 6. Database Dependency
def get_db():
    connection = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        yield connection
    finally:
        connection.close()

# 7. Token 驗證依賴 (結合 Redis 快取)
async def verify_firebase_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Header 格式錯誤，需為 Bearer <Token>")
    
    id_token = authorization.split("Bearer ")[1]
    
    cached_uid = redis_client.get(f"token:{id_token}")
    if cached_uid:
        return cached_uid

    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        redis_client.setex(f"token:{id_token}", 1800, uid)
        return uid
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token 驗證失敗: {str(e)}")

# 8. API 路由：登入與玩家資料同步
@app.post("/api/login")
async def login_and_sync(authorization: str = Header(...), db=Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token header")
    
    id_token = authorization.split("Bearer ")[1]
    
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email', 'no-email@game.com')
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token 驗證無效: {str(e)}")

    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM players WHERE firebase_uid = %s", (uid,))
        player = cursor.fetchone()

        if not player:
            cursor.execute(
                "INSERT INTO players (firebase_uid, email) VALUES (%s, %s)",
                (uid, email)
            )
            db.commit()
            cursor.execute("SELECT * FROM players WHERE firebase_uid = %s", (uid,))
            player = cursor.fetchone()

    redis_client.set(f"session:{uid}", "online")

    return {
        "status": "success",
        "message": "驗證成功並同步資料庫",
        "player": player
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)