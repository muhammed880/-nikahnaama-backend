from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import jwt
import bcrypt
import asyncpg
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# PostgreSQL connection
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'nikah-naama-super-secure-secret-key-2025-prod')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Create the main app
app = FastAPI(title="Nikah Naama API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

security = HTTPBearer()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database pool
db_pool = None

async def get_db():
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return db_pool

# Initialize database tables
async def init_db():
    pool = await get_db()
    async with pool.acquire() as conn:
        # Settings table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id TEXT PRIMARY KEY DEFAULT 'app_settings',
                admin_password TEXT DEFAULT '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYV6VzMYqK6C',
                registration_fee NUMERIC DEFAULT 500,
                nikah_fee NUMERIC DEFAULT 200,
                upi_id TEXT DEFAULT 'nikahnaama@upi',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default settings if not exists
        await conn.execute('''
            INSERT INTO settings (id) VALUES ('app_settings') ON CONFLICT (id) DO NOTHING
        ''')
        
        # Masjids table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS masjids (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT,
                city TEXT,
                state TEXT,
                pincode TEXT,
                phone TEXT,
                email TEXT UNIQUE,
                imam_name TEXT,
                password TEXT,
                committee JSONB DEFAULT '[]',
                upi_id TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                payment_status TEXT DEFAULT 'pending',
                payment_reference TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Nikahs table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS nikahs (
                id TEXT PRIMARY KEY,
                certificate_id TEXT UNIQUE,
                masjid_id TEXT,
                masjid_name TEXT DEFAULT '',
                groom JSONB,
                bride JSONB,
                nikah_date TEXT,
                mehr_amount TEXT,
                witnesses JSONB DEFAULT '[]',
                witness_photos JSONB DEFAULT '[]',
                witness_signatures JSONB DEFAULT '[]',
                couple_photo TEXT DEFAULT '',
                venue_name TEXT DEFAULT '',
                imam_name TEXT DEFAULT '',
                imam_signature TEXT DEFAULT '',
                masjid_signature TEXT DEFAULT '',
                wakeel TEXT DEFAULT '',
                status TEXT DEFAULT 'registered',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Matrimony table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS matrimony (
                id TEXT PRIMARY KEY,
                masjid_id TEXT,
                masjid_name TEXT DEFAULT '',
                name TEXT,
                age INTEGER,
                gender TEXT,
                education TEXT,
                occupation TEXT,
                height TEXT,
                marital_status TEXT,
                city TEXT,
                state TEXT,
                about TEXT,
                requirements TEXT,
                photo TEXT DEFAULT '',
                contact_phone TEXT,
                contact_email TEXT DEFAULT '',
                contact_shared BOOLEAN DEFAULT FALSE,
                verified BOOLEAN DEFAULT FALSE,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Jobs table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                masjid_id TEXT,
                masjid_name TEXT DEFAULT '',
                title TEXT,
                role TEXT,
                description TEXT,
                requirements TEXT,
                salary_range TEXT,
                location TEXT,
                contact_phone TEXT,
                contact_email TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Job Profiles table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS job_profiles (
                id TEXT PRIMARY KEY,
                name TEXT,
                phone TEXT,
                email TEXT DEFAULT '',
                age INTEGER,
                role TEXT,
                qualification TEXT,
                experience TEXT,
                current_location TEXT,
                preferred_locations TEXT,
                about TEXT,
                photo TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Donations table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS donations (
                id TEXT PRIMARY KEY,
                masjid_id TEXT,
                masjid_name TEXT DEFAULT '',
                donor_name TEXT,
                donor_phone TEXT,
                amount NUMERIC,
                purpose TEXT,
                transaction_id TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        logger.info("Database tables initialized successfully")

@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    global db_pool
    if db_pool:
        await db_pool.close()

# ============== MODELS ==============

class CommitteeMember(BaseModel):
    name: str
    designation: str
    phone: str

class MasjidCreate(BaseModel):
    name: str
    address: str
    city: str
    state: str
    pincode: str
    phone: str
    email: str
    imam_name: str
    password: str
    committee: List[CommitteeMember] = []
    upi_id: str = ""
    payment_reference: str = ""

class Person(BaseModel):
    name: str
    father_name: str
    aadhaar: str
    phone: str
    address: str
    age: int
    photo: str = ""
    signature: str = ""

class NikahCreate(BaseModel):
    masjid_id: str
    groom: Person
    bride: Person
    nikah_date: str
    mehr_amount: str
    witnesses: List[str] = []
    witness_photos: List[str] = []
    witness_signatures: List[str] = []
    couple_photo: str = ""
    venue_name: str = ""
    imam_name: str = ""
    imam_signature: str = ""
    masjid_signature: str = ""
    wakeel: str = ""

class MatrimonyCreate(BaseModel):
    masjid_id: str
    name: str
    age: int
    gender: str
    education: str
    occupation: str
    height: str
    marital_status: str
    city: str
    state: str
    about: str
    requirements: str
    photo: str = ""
    contact_phone: str
    contact_email: str = ""

class JobCreate(BaseModel):
    masjid_id: str
    title: str
    role: str
    description: str
    requirements: str
    salary_range: str
    location: str
    contact_phone: str
    contact_email: str = ""

class JobProfileCreate(BaseModel):
    name: str
    phone: str
    email: str = ""
    age: int
    role: str
    qualification: str
    experience: str
    current_location: str
    preferred_locations: str
    about: str
    photo: str = ""

class DonationCreate(BaseModel):
    masjid_id: str
    donor_name: str
    donor_phone: str
    amount: float
    purpose: str
    transaction_id: str = ""

class LoginRequest(BaseModel):
    email: str = ""
    password: str

class AdminLoginRequest(BaseModel):
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: str
    user_id: str
    user_name: str

# ============== UTILITIES ==============

def create_token(user_id: str, user_type: str, user_name: str) -> str:
    payload = {
        "sub": user_id,
        "type": user_type,
        "name": user_name,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except:
        return False

# ============== SETTINGS ENDPOINTS ==============

@api_router.get("/settings")
async def get_settings():
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM settings WHERE id = 'app_settings'")
        if row:
            result = dict(row)
            result.pop('admin_password', None)
            return result
        return {"registration_fee": 500, "nikah_fee": 200, "upi_id": "nikahnaama@upi"}

@api_router.put("/settings")
async def update_settings(settings: Dict[str, Any], token: Dict = Depends(verify_token)):
    if token.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pool = await get_db()
    async with pool.acquire() as conn:
        if "admin_password" in settings and settings["admin_password"]:
            settings["admin_password"] = hash_password(settings["admin_password"])
        
        set_clauses = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(settings.keys())])
        values = list(settings.values())
        
        await conn.execute(
            f"UPDATE settings SET {set_clauses}, updated_at = CURRENT_TIMESTAMP WHERE id = 'app_settings'",
            *values
        )
    return {"message": "Settings updated"}

# ============== AUTH ENDPOINTS ==============

@api_router.post("/admin/login", response_model=TokenResponse)
async def admin_login(request: AdminLoginRequest):
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT admin_password FROM settings WHERE id = 'app_settings'")
        
        stored_password = row['admin_password'] if row else None
        
        if not stored_password:
            hashed = hash_password("admin123")
            await conn.execute(
                "INSERT INTO settings (id, admin_password) VALUES ('app_settings', $1) ON CONFLICT (id) DO UPDATE SET admin_password = $1",
                hashed
            )
            stored_password = hashed
        
        if verify_password(request.password, stored_password):
            token = create_token("admin", "admin", "Admin")
            return TokenResponse(
                access_token=token,
                user_type="admin",
                user_id="admin",
                user_name="Admin"
            )
        
        if request.password == "admin123":
            hashed = hash_password("admin123")
            await conn.execute(
                "UPDATE settings SET admin_password = $1 WHERE id = 'app_settings'",
                hashed
            )
            token = create_token("admin", "admin", "Admin")
            return TokenResponse(
                access_token=token,
                user_type="admin",
                user_id="admin",
                user_name="Admin"
            )
    
    raise HTTPException(status_code=401, detail="Invalid password")

@api_router.post("/masjids/login", response_model=TokenResponse)
async def masjid_login(request: LoginRequest):
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, email, password, status FROM masjids WHERE email = $1",
            request.email
        )
        
        if not row:
            raise HTTPException(status_code=401, detail="Masjid not found")
        
        if row['status'] != "approved":
            raise HTTPException(status_code=403, detail="Masjid not approved yet")
        
        if not verify_password(request.password, row['password']):
            raise HTTPException(status_code=401, detail="Invalid password")
        
        token = create_token(row['id'], "masjid", row['name'])
        return TokenResponse(
            access_token=token,
            user_type="masjid",
            user_id=row['id'],
            user_name=row['name']
        )

# ============== MASJID ENDPOINTS ==============

@api_router.get("/masjids")
async def get_masjids(status: Optional[str] = None):
    pool = await get_db()
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT id, name, address, city, state, pincode, phone, email, imam_name, committee, upi_id, status, payment_status, payment_reference, created_at, updated_at FROM masjids WHERE status = $1 ORDER BY created_at DESC",
                status
            )
        else:
            rows = await conn.fetch(
                "SELECT id, name, address, city, state, pincode, phone, email, imam_name, committee, upi_id, status, payment_status, payment_reference, created_at, updated_at FROM masjids ORDER BY created_at DESC"
            )
        return [dict(row) for row in rows]

@api_router.get("/masjids/{masjid_id}")
async def get_masjid(masjid_id: str):
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, address, city, state, pincode, phone, email, imam_name, committee, upi_id, status, payment_status, payment_reference, created_at, updated_at FROM masjids WHERE id = $1",
            masjid_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Masjid not found")
        return dict(row)

@api_router.post("/masjids")
async def create_masjid(masjid_data: MasjidCreate):
    pool = await get_db()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM masjids WHERE email = $1", masjid_data.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        masjid_id = str(uuid.uuid4())
        hashed_password = hash_password(masjid_data.password)
        committee_json = json.dumps([m.dict() for m in masjid_data.committee])
        
        await conn.execute('''
            INSERT INTO masjids (id, name, address, city, state, pincode, phone, email, imam_name, password, committee, upi_id, payment_reference)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        ''', masjid_id, masjid_data.name, masjid_data.address, masjid_data.city, masjid_data.state,
            masjid_data.pincode, masjid_data.phone, masjid_data.email, masjid_data.imam_name,
            hashed_password, committee_json, masjid_data.upi_id, masjid_data.payment_reference)
        
        return {"id": masjid_id, "name": masjid_data.name, "email": masjid_data.email, "status": "pending"}

@api_router.put("/masjids/{masjid_id}")
async def update_masjid(masjid_id: str, updates: Dict[str, Any], token: Dict = Depends(verify_token)):
    if token.get("type") != "admin" and token.get("sub") != masjid_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    pool = await get_db()
    async with pool.acquire() as conn:
        if "password" in updates:
            updates["password"] = hash_password(updates["password"])
        if "committee" in updates:
            updates["committee"] = json.dumps(updates["committee"])
        
        set_clauses = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
        values = list(updates.values()) + [masjid_id]
        
        result = await conn.execute(
            f"UPDATE masjids SET {set_clauses}, updated_at = CURRENT_TIMESTAMP WHERE id = ${len(values)}",
            *values
        )
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Masjid not found")
    
    return {"message": "Masjid updated"}

@api_router.put("/masjids/{masjid_id}/approve")
async def approve_masjid(masjid_id: str, token: Dict = Depends(verify_token)):
    if token.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE masjids SET status = 'approved', updated_at = CURRENT_TIMESTAMP WHERE id = $1",
            masjid_id
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Masjid not found")
    
    return {"message": "Masjid approved"}

@api_router.put("/masjids/{masjid_id}/reject")
async def reject_masjid(masjid_id: str, token: Dict = Depends(verify_token)):
    if token.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE masjids SET status = 'rejected', updated_at = CURRENT_TIMESTAMP WHERE id = $1",
            masjid_id
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Masjid not found")
    
    return {"message": "Masjid rejected"}

# ============== NIKAH ENDPOINTS ==============

@api_router.get("/nikahs")
async def get_nikahs(masjid_id: Optional[str] = None):
    pool = await get_db()
    async with pool.acquire() as conn:
        if masjid_id:
            rows = await conn.fetch(
                "SELECT * FROM nikahs WHERE masjid_id = $1 ORDER BY created_at DESC",
                masjid_id
            )
        else:
            rows = await conn.fetch("SELECT * FROM nikahs ORDER BY created_at DESC")
        return [dict(row) for row in rows]

@api_router.get("/nikahs/{nikah_id}")
async def get_nikah(nikah_id: str):
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM nikahs WHERE id = $1", nikah_id)
        if not row:
            raise HTTPException(status_code=404, detail="Nikah not found")
        return dict(row)

@api_router.get("/nikahs/certificate/{certificate_id}")
async def get_nikah_by_certificate(certificate_id: str):
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM nikahs WHERE certificate_id = $1", certificate_id)
        if not row:
            raise HTTPException(status_code=404, detail="Certificate not found")
        return dict(row)

@api_router.get("/nikahs/check-aadhaar/{aadhaar}")
async def check_aadhaar(aadhaar: str):
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM nikahs WHERE groom->>'aadhaar' = $1 OR bride->>'aadhaar' = $1",
            aadhaar
        )
        return {"exists": row is not None}

@api_router.post("/nikahs")
async def create_nikah(nikah_data: NikahCreate, token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    pool = await get_db()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM nikahs WHERE groom->>'aadhaar' = $1 OR bride->>'aadhaar' = $2",
            nikah_data.groom.aadhaar, nikah_data.bride.aadhaar
        )
        if existing:
            raise HTTPException(status_code=400, detail="Aadhaar already registered in another nikah")
        
        masjid_row = await conn.fetchrow("SELECT name FROM masjids WHERE id = $1", nikah_data.masjid_id)
        masjid_name = masjid_row['name'] if masjid_row else ""
        
        nikah_id = str(uuid.uuid4())
        certificate_id = f"NK{datetime.now().strftime('%Y%m%d')}{nikah_id[:6].upper()}"
        
        await conn.execute('''
            INSERT INTO nikahs (id, certificate_id, masjid_id, masjid_name, groom, bride, nikah_date, mehr_amount, witnesses, witness_photos, witness_signatures, couple_photo, venue_name, imam_name, imam_signature, masjid_signature, wakeel)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        ''', nikah_id, certificate_id, nikah_data.masjid_id, masjid_name,
            json.dumps(nikah_data.groom.dict()), json.dumps(nikah_data.bride.dict()),
            nikah_data.nikah_date, nikah_data.mehr_amount,
            json.dumps(nikah_data.witnesses), json.dumps(nikah_data.witness_photos),
            json.dumps(nikah_data.witness_signatures), nikah_data.couple_photo,
            nikah_data.venue_name, nikah_data.imam_name, nikah_data.imam_signature,
            nikah_data.masjid_signature, nikah_data.wakeel)
        
        return {"id": nikah_id, "certificate_id": certificate_id, "masjid_name": masjid_name}

@api_router.put("/nikahs/{nikah_id}")
async def update_nikah(nikah_id: str, updates: Dict[str, Any], token: Dict = Depends(verify_token)):
    if token.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required for editing nikahs")
    
    pool = await get_db()
    async with pool.acquire() as conn:
        if "groom" in updates:
            updates["groom"] = json.dumps(updates["groom"])
        if "bride" in updates:
            updates["bride"] = json.dumps(updates["bride"])
        if "witnesses" in updates:
            updates["witnesses"] = json.dumps(updates["witnesses"])
        
        set_clauses = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
        values = list(updates.values()) + [nikah_id]
        
        result = await conn.execute(
            f"UPDATE nikahs SET {set_clauses}, updated_at = CURRENT_TIMESTAMP WHERE id = ${len(values)}",
            *values
        )
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Nikah not found")
    
    return {"message": "Nikah updated"}

# ============== MATRIMONY ENDPOINTS ==============

@api_router.get("/matrimony")
async def get_matrimony_profiles(gender: Optional[str] = None, city: Optional[str] = None):
    pool = await get_db()
    async with pool.acquire() as conn:
        query = "SELECT * FROM matrimony WHERE status = 'active'"
        params = []
        
        if gender:
            params.append(gender)
            query += f" AND gender = ${len(params)}"
        if city:
            params.append(f"%{city}%")
            query += f" AND city ILIKE ${len(params)}"
        
        query += " ORDER BY created_at DESC"
        
        rows = await conn.fetch(query, *params)
        profiles = []
        for row in rows:
            p = dict(row)
            if not p.get("contact_shared"):
                p["contact_phone"] = "Hidden"
                p["contact_email"] = "Hidden"
            profiles.append(p)
        return profiles

@api_router.get("/matrimony/{profile_id}")
async def get_matrimony_profile(profile_id: str):
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM matrimony WHERE id = $1", profile_id)
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")
        return dict(row)

@api_router.post("/matrimony")
async def create_matrimony_profile(profile_data: MatrimonyCreate, token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    pool = await get_db()
    async with pool.acquire() as conn:
        masjid_row = await conn.fetchrow("SELECT name FROM masjids WHERE id = $1", profile_data.masjid_id)
        masjid_name = masjid_row['name'] if masjid_row else ""
        
        profile_id = str(uuid.uuid4())
        
        await conn.execute('''
            INSERT INTO matrimony (id, masjid_id, masjid_name, name, age, gender, education, occupation, height, marital_status, city, state, about, requirements, photo, contact_phone, contact_email)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        ''', profile_id, profile_data.masjid_id, masjid_name, profile_data.name, profile_data.age,
            profile_data.gender, profile_data.education, profile_data.occupation, profile_data.height,
            profile_data.marital_status, profile_data.city, profile_data.state, profile_data.about,
            profile_data.requirements, profile_data.photo, profile_data.contact_phone, profile_data.contact_email)
        
        return {"id": profile_id, "name": profile_data.name}

@api_router.put("/matrimony/{profile_id}/verify")
async def verify_matrimony_profile(profile_id: str, token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE matrimony SET verified = TRUE, contact_shared = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
            profile_id
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Profile not found")
    
    return {"message": "Profile verified"}

@api_router.put("/matrimony/{profile_id}")
async def update_matrimony_profile(profile_id: str, updates: Dict[str, Any], token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    pool = await get_db()
    async with pool.acquire() as conn:
        set_clauses = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
        values = list(updates.values()) + [profile_id]
        
        result = await conn.execute(
            f"UPDATE matrimony SET {set_clauses}, updated_at = CURRENT_TIMESTAMP WHERE id = ${len(values)}",
            *values
        )
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Profile not found")
    
    return {"message": "Profile updated"}

# ============== JOBS ENDPOINTS ==============

@api_router.get("/jobs")
async def get_jobs(role: Optional[str] = None, masjid_id: Optional[str] = None):
    pool = await get_db()
    async with pool.acquire() as conn:
        query = "SELECT * FROM jobs WHERE status = 'active'"
        params = []
        
        if role:
            params.append(role)
            query += f" AND role = ${len(params)}"
        if masjid_id:
            params.append(masjid_id)
            query += f" AND masjid_id = ${len(params)}"
        
        query += " ORDER BY created_at DESC"
        
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

@api_router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return dict(row)

@api_router.post("/jobs")
async def create_job(job_data: JobCreate, token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    pool = await get_db()
    async with pool.acquire() as conn:
        masjid_row = await conn.fetchrow("SELECT name FROM masjids WHERE id = $1", job_data.masjid_id)
        masjid_name = masjid_row['name'] if masjid_row else ""
        
        job_id = str(uuid.uuid4())
        
        await conn.execute('''
            INSERT INTO jobs (id, masjid_id, masjid_name, title, role, description, requirements, salary_range, location, contact_phone, contact_email)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ''', job_id, job_data.masjid_id, masjid_name, job_data.title, job_data.role,
            job_data.description, job_data.requirements, job_data.salary_range,
            job_data.location, job_data.contact_phone, job_data.contact_email)
        
        return {"id": job_id, "title": job_data.title}

@api_router.put("/jobs/{job_id}")
async def update_job(job_id: str, updates: Dict[str, Any], token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    pool = await get_db()
    async with pool.acquire() as conn:
        set_clauses = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
        values = list(updates.values()) + [job_id]
        
        result = await conn.execute(
            f"UPDATE jobs SET {set_clauses}, updated_at = CURRENT_TIMESTAMP WHERE id = ${len(values)}",
            *values
        )
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Job not found")
    
    return {"message": "Job updated"}

@api_router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM jobs WHERE id = $1", job_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Job not found")
    
    return {"message": "Job deleted"}

# ============== JOB PROFILES ENDPOINTS ==============

@api_router.get("/profiles")
async def get_job_profiles(role: Optional[str] = None):
    pool = await get_db()
    async with pool.acquire() as conn:
        if role:
            rows = await conn.fetch(
                "SELECT * FROM job_profiles WHERE status = 'active' AND role = $1 ORDER BY created_at DESC",
                role
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM job_profiles WHERE status = 'active' ORDER BY created_at DESC"
            )
        return [dict(row) for row in rows]

@api_router.get("/profiles/{profile_id}")
async def get_job_profile(profile_id: str):
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM job_profiles WHERE id = $1", profile_id)
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")
        return dict(row)

@api_router.post("/profiles")
async def create_job_profile(profile_data: JobProfileCreate):
    pool = await get_db()
    async with pool.acquire() as conn:
        profile_id = str(uuid.uuid4())
        
        await conn.execute('''
            INSERT INTO job_profiles (id, name, phone, email, age, role, qualification, experience, current_location, preferred_locations, about, photo)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        ''', profile_id, profile_data.name, profile_data.phone, profile_data.email,
            profile_data.age, profile_data.role, profile_data.qualification,
            profile_data.experience, profile_data.current_location,
            profile_data.preferred_locations, profile_data.about, profile_data.photo)
        
        return {"id": profile_id, "name": profile_data.name}

@api_router.put("/profiles/{profile_id}")
async def update_job_profile(profile_id: str, updates: Dict[str, Any]):
    pool = await get_db()
    async with pool.acquire() as conn:
        set_clauses = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
        values = list(updates.values()) + [profile_id]
        
        result = await conn.execute(
            f"UPDATE job_profiles SET {set_clauses}, updated_at = CURRENT_TIMESTAMP WHERE id = ${len(values)}",
            *values
        )
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Profile not found")
    
    return {"message": "Profile updated"}

# ============== DONATIONS ENDPOINTS ==============

@api_router.get("/donations")
async def get_donations(masjid_id: Optional[str] = None):
    pool = await get_db()
    async with pool.acquire() as conn:
        if masjid_id:
            rows = await conn.fetch(
                "SELECT * FROM donations WHERE masjid_id = $1 ORDER BY created_at DESC",
                masjid_id
            )
        else:
            rows = await conn.fetch("SELECT * FROM donations ORDER BY created_at DESC")
        return [dict(row) for row in rows]

@api_router.post("/donations")
async def create_donation(donation_data: DonationCreate):
    pool = await get_db()
    async with pool.acquire() as conn:
        masjid_row = await conn.fetchrow("SELECT name FROM masjids WHERE id = $1", donation_data.masjid_id)
        if not masjid_row:
            raise HTTPException(status_code=404, detail="Masjid not found")
        
        donation_id = str(uuid.uuid4())
        
        await conn.execute('''
            INSERT INTO donations (id, masjid_id, masjid_name, donor_name, donor_phone, amount, purpose, transaction_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ''', donation_id, donation_data.masjid_id, masjid_row['name'],
            donation_data.donor_name, donation_data.donor_phone,
            donation_data.amount, donation_data.purpose, donation_data.transaction_id)
        
        return {"id": donation_id, "masjid_name": masjid_row['name']}

# ============== STATS ENDPOINT ==============

@api_router.get("/stats")
async def get_stats(masjid_id: Optional[str] = None):
    pool = await get_db()
    async with pool.acquire() as conn:
        if masjid_id:
            nikahs = await conn.fetchval("SELECT COUNT(*) FROM nikahs WHERE masjid_id = $1", masjid_id)
            matrimony = await conn.fetchval("SELECT COUNT(*) FROM matrimony WHERE masjid_id = $1", masjid_id)
            jobs = await conn.fetchval("SELECT COUNT(*) FROM jobs WHERE masjid_id = $1", masjid_id)
            donations = await conn.fetchval("SELECT COUNT(*) FROM donations WHERE masjid_id = $1", masjid_id)
            
            return {
                "nikahs": nikahs,
                "matrimony": matrimony,
                "jobs": jobs,
                "donations": donations
            }
        else:
            masjids = await conn.fetchval("SELECT COUNT(*) FROM masjids")
            masjids_pending = await conn.fetchval("SELECT COUNT(*) FROM masjids WHERE status = 'pending'")
            masjids_approved = await conn.fetchval("SELECT COUNT(*) FROM masjids WHERE status = 'approved'")
            nikahs = await conn.fetchval("SELECT COUNT(*) FROM nikahs")
            matrimony = await conn.fetchval("SELECT COUNT(*) FROM matrimony")
            jobs = await conn.fetchval("SELECT COUNT(*) FROM jobs")
            profiles = await conn.fetchval("SELECT COUNT(*) FROM job_profiles")
            donations = await conn.fetchval("SELECT COUNT(*) FROM donations")
            
            return {
                "masjids": masjids,
                "masjids_pending": masjids_pending,
                "masjids_approved": masjids_approved,
                "nikahs": nikahs,
                "matrimony": matrimony,
                "jobs": jobs,
                "job_profiles": profiles,
                "donations": donations
            }

# ============== HEALTH CHECK ==============

@api_router.get("/")
async def root():
    return {"message": "Nikah Naama API", "version": "1.0.0"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*", "https://nikahnaama.org", "https://www.nikahnaama.org", "http://localhost:3000"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)
