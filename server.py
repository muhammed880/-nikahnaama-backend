from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import jwt
import bcrypt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'nikah_naama')]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'nikah-naama-secret-key-2025')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Create the main app
app = FastAPI(title="Nikah Naama API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

security = HTTPBearer()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============== MODELS ==============

class Settings(BaseModel):
    id: str = Field(default="app_settings")
    admin_password: str = Field(default="admin123")
    registration_fee: float = Field(default=500.0)
    nikah_fee: float = Field(default=200.0)
    upi_id: str = Field(default="nikahnaama@upi")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CommitteeMember(BaseModel):
    name: str
    designation: str
    phone: str

class Masjid(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    address: str
    city: str
    state: str
    pincode: str
    phone: str
    email: str
    imam_name: str
    password: str = ""
    committee: List[CommitteeMember] = []
    upi_id: str = ""  # For donations
    status: str = Field(default="pending")  # pending, approved, rejected
    payment_status: str = Field(default="pending")  # pending, paid
    payment_reference: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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
    photo: str = ""  # Base64 photo for records
    signature: str = ""  # Base64 signature

class Nikah(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    certificate_id: str = Field(default_factory=lambda: f"NK{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}")
    masjid_id: str
    masjid_name: str = ""
    groom: Person
    bride: Person
    nikah_date: str
    mehr_amount: str
    witnesses: List[str] = []
    witness_photos: List[str] = []  # Base64 photos
    witness_signatures: List[str] = []  # Base64 signatures
    couple_photo: str = ""  # Base64
    venue_name: str = ""
    imam_name: str = ""
    imam_signature: str = ""  # Base64 signature
    masjid_signature: str = ""  # Base64 signature/stamp
    wakeel: str = ""
    status: str = Field(default="registered")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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

class MatrimonyProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    masjid_id: str
    masjid_name: str = ""
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
    photo: str = ""  # Base64
    contact_phone: str
    contact_email: str = ""
    contact_shared: bool = Field(default=False)
    verified: bool = Field(default=False)
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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

class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    masjid_id: str
    masjid_name: str = ""
    title: str
    role: str  # Aalim, Hafiz, Qari, Mufti, Muezzin
    description: str
    requirements: str
    salary_range: str
    location: str
    contact_phone: str
    contact_email: str = ""
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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

class JobProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str
    email: str = ""
    age: int
    role: str  # Aalim, Hafiz, Qari, Mufti, Muezzin
    qualification: str
    experience: str
    current_location: str
    preferred_locations: str
    about: str
    photo: str = ""  # Base64
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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

class Donation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    masjid_id: str
    masjid_name: str = ""
    donor_name: str
    donor_phone: str
    amount: float
    purpose: str
    transaction_id: str = ""
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=datetime.utcnow)

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
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ============== SETTINGS ENDPOINTS ==============

@api_router.get("/settings")
async def get_settings():
    settings = await db.settings.find_one({"id": "app_settings"})
    if not settings:
        # Create default settings
        default_settings = Settings()
        await db.settings.insert_one(default_settings.dict())
        settings = default_settings.dict()
    # Don't return the admin password
    settings.pop('admin_password', None)
    settings.pop('_id', None)
    return settings

@api_router.put("/settings")
async def update_settings(settings: Dict[str, Any], token: Dict = Depends(verify_token)):
    if token.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    settings["updated_at"] = datetime.utcnow()
    if "admin_password" in settings and settings["admin_password"]:
        settings["admin_password"] = hash_password(settings["admin_password"])
    
    await db.settings.update_one(
        {"id": "app_settings"},
        {"$set": settings},
        upsert=True
    )
    return {"message": "Settings updated"}

# ============== AUTH ENDPOINTS ==============

@api_router.post("/admin/login", response_model=TokenResponse)
async def admin_login(request: AdminLoginRequest):
    settings = await db.settings.find_one({"id": "app_settings"})
    
    if not settings:
        # Create default settings with hashed password
        default_settings = Settings()
        default_settings.admin_password = hash_password("admin123")
        await db.settings.insert_one(default_settings.dict())
        settings = default_settings.dict()
    
    # Check if password is hashed or plain (for migration)
    stored_password = settings.get("admin_password", "admin123")
    
    try:
        # Try to verify as hashed password
        if verify_password(request.password, stored_password):
            token = create_token("admin", "admin", "Admin")
            return TokenResponse(
                access_token=token,
                user_type="admin",
                user_id="admin",
                user_name="Admin"
            )
    except:
        # If verification fails, check plain text (for first time)
        if request.password == stored_password:
            # Hash the password for future use
            await db.settings.update_one(
                {"id": "app_settings"},
                {"$set": {"admin_password": hash_password(stored_password)}}
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
    masjid = await db.masjids.find_one({"email": request.email})
    
    if not masjid:
        raise HTTPException(status_code=401, detail="Masjid not found")
    
    if masjid.get("status") != "approved":
        raise HTTPException(status_code=403, detail="Masjid not approved yet")
    
    if not verify_password(request.password, masjid.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    token = create_token(masjid["id"], "masjid", masjid["name"])
    return TokenResponse(
        access_token=token,
        user_type="masjid",
        user_id=masjid["id"],
        user_name=masjid["name"]
    )

# ============== MASJID ENDPOINTS ==============

@api_router.get("/masjids")
async def get_masjids(status: Optional[str] = None):
    query = {}
    if status:
        query["status"] = status
    
    masjids = await db.masjids.find(query).to_list(1000)
    for m in masjids:
        m.pop('_id', None)
        m.pop('password', None)
    return masjids

@api_router.get("/masjids/{masjid_id}")
async def get_masjid(masjid_id: str):
    masjid = await db.masjids.find_one({"id": masjid_id})
    if not masjid:
        raise HTTPException(status_code=404, detail="Masjid not found")
    masjid.pop('_id', None)
    masjid.pop('password', None)
    return masjid

@api_router.post("/masjids")
async def create_masjid(masjid_data: MasjidCreate):
    # Check if email already exists
    existing = await db.masjids.find_one({"email": masjid_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    masjid = Masjid(**masjid_data.dict())
    masjid.password = hash_password(masjid_data.password)
    
    await db.masjids.insert_one(masjid.dict())
    
    result = masjid.dict()
    result.pop('password', None)
    return result

@api_router.put("/masjids/{masjid_id}")
async def update_masjid(masjid_id: str, updates: Dict[str, Any], token: Dict = Depends(verify_token)):
    if token.get("type") != "admin" and token.get("sub") != masjid_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    updates["updated_at"] = datetime.utcnow()
    if "password" in updates:
        updates["password"] = hash_password(updates["password"])
    
    result = await db.masjids.update_one(
        {"id": masjid_id},
        {"$set": updates}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Masjid not found")
    
    return {"message": "Masjid updated"}

@api_router.put("/masjids/{masjid_id}/approve")
async def approve_masjid(masjid_id: str, token: Dict = Depends(verify_token)):
    if token.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.masjids.update_one(
        {"id": masjid_id},
        {"$set": {"status": "approved", "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Masjid not found")
    
    return {"message": "Masjid approved"}

@api_router.put("/masjids/{masjid_id}/reject")
async def reject_masjid(masjid_id: str, token: Dict = Depends(verify_token)):
    if token.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.masjids.update_one(
        {"id": masjid_id},
        {"$set": {"status": "rejected", "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Masjid not found")
    
    return {"message": "Masjid rejected"}

# ============== NIKAH ENDPOINTS ==============

@api_router.get("/nikahs")
async def get_nikahs(masjid_id: Optional[str] = None):
    query = {}
    if masjid_id:
        query["masjid_id"] = masjid_id
    
    nikahs = await db.nikahs.find(query).sort("created_at", -1).to_list(1000)
    for n in nikahs:
        n.pop('_id', None)
    return nikahs

@api_router.get("/nikahs/{nikah_id}")
async def get_nikah(nikah_id: str):
    nikah = await db.nikahs.find_one({"id": nikah_id})
    if not nikah:
        raise HTTPException(status_code=404, detail="Nikah not found")
    nikah.pop('_id', None)
    return nikah

@api_router.get("/nikahs/certificate/{certificate_id}")
async def get_nikah_by_certificate(certificate_id: str):
    nikah = await db.nikahs.find_one({"certificate_id": certificate_id})
    if not nikah:
        raise HTTPException(status_code=404, detail="Certificate not found")
    nikah.pop('_id', None)
    return nikah

@api_router.get("/nikahs/check-aadhaar/{aadhaar}")
async def check_aadhaar(aadhaar: str):
    # Check if aadhaar exists in any nikah record
    nikah = await db.nikahs.find_one({
        "$or": [
            {"groom.aadhaar": aadhaar},
            {"bride.aadhaar": aadhaar}
        ]
    })
    return {"exists": nikah is not None}

@api_router.post("/nikahs")
async def create_nikah(nikah_data: NikahCreate, token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check Aadhaar duplicates
    existing = await db.nikahs.find_one({
        "$or": [
            {"groom.aadhaar": nikah_data.groom.aadhaar},
            {"bride.aadhaar": nikah_data.bride.aadhaar}
        ]
    })
    if existing:
        raise HTTPException(status_code=400, detail="Aadhaar already registered in another nikah")
    
    # Get masjid name
    masjid = await db.masjids.find_one({"id": nikah_data.masjid_id})
    masjid_name = masjid["name"] if masjid else ""
    
    nikah = Nikah(**nikah_data.dict())
    nikah.masjid_name = masjid_name
    nikah.venue_name = nikah_data.venue_name
    nikah.imam_name = nikah_data.imam_name
    nikah.imam_signature = nikah_data.imam_signature
    nikah.masjid_signature = nikah_data.masjid_signature
    nikah.wakeel = nikah_data.wakeel
    nikah.witness_photos = nikah_data.witness_photos
    nikah.witness_signatures = nikah_data.witness_signatures
    
    await db.nikahs.insert_one(nikah.dict())
    
    result = nikah.dict()
    result.pop('_id', None)
    return result

@api_router.put("/nikahs/{nikah_id}")
async def update_nikah(nikah_id: str, updates: Dict[str, Any], token: Dict = Depends(verify_token)):
    if token.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required for editing nikahs")
    
    updates["updated_at"] = datetime.utcnow()
    
    result = await db.nikahs.update_one(
        {"id": nikah_id},
        {"$set": updates}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Nikah not found")
    
    return {"message": "Nikah updated"}

# ============== MATRIMONY ENDPOINTS ==============

@api_router.get("/matrimony")
async def get_matrimony_profiles(gender: Optional[str] = None, city: Optional[str] = None):
    query = {"status": "active"}
    if gender:
        query["gender"] = gender
    if city:
        query["city"] = {"$regex": city, "$options": "i"}
    
    profiles = await db.matrimony.find(query).sort("created_at", -1).to_list(1000)
    for p in profiles:
        p.pop('_id', None)
        # Hide contact info unless verified
        if not p.get("contact_shared"):
            p["contact_phone"] = "Hidden"
            p["contact_email"] = "Hidden"
    return profiles

@api_router.get("/matrimony/{profile_id}")
async def get_matrimony_profile(profile_id: str):
    profile = await db.matrimony.find_one({"id": profile_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.pop('_id', None)
    return profile

@api_router.post("/matrimony")
async def create_matrimony_profile(profile_data: MatrimonyCreate, token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get masjid name
    masjid = await db.masjids.find_one({"id": profile_data.masjid_id})
    masjid_name = masjid["name"] if masjid else ""
    
    profile = MatrimonyProfile(**profile_data.dict())
    profile.masjid_name = masjid_name
    
    await db.matrimony.insert_one(profile.dict())
    
    result = profile.dict()
    result.pop('_id', None)
    return result

@api_router.put("/matrimony/{profile_id}/verify")
async def verify_matrimony_profile(profile_id: str, token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.matrimony.update_one(
        {"id": profile_id},
        {"$set": {"verified": True, "contact_shared": True, "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return {"message": "Profile verified"}

@api_router.put("/matrimony/{profile_id}")
async def update_matrimony_profile(profile_id: str, updates: Dict[str, Any], token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    updates["updated_at"] = datetime.utcnow()
    
    result = await db.matrimony.update_one(
        {"id": profile_id},
        {"$set": updates}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return {"message": "Profile updated"}

# ============== JOBS ENDPOINTS ==============

@api_router.get("/jobs")
async def get_jobs(role: Optional[str] = None, masjid_id: Optional[str] = None):
    query = {"status": "active"}
    if role:
        query["role"] = role
    if masjid_id:
        query["masjid_id"] = masjid_id
    
    jobs = await db.jobs.find(query).sort("created_at", -1).to_list(1000)
    for j in jobs:
        j.pop('_id', None)
    return jobs

@api_router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = await db.jobs.find_one({"id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.pop('_id', None)
    return job

@api_router.post("/jobs")
async def create_job(job_data: JobCreate, token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get masjid name
    masjid = await db.masjids.find_one({"id": job_data.masjid_id})
    masjid_name = masjid["name"] if masjid else ""
    
    job = Job(**job_data.dict())
    job.masjid_name = masjid_name
    
    await db.jobs.insert_one(job.dict())
    
    result = job.dict()
    result.pop('_id', None)
    return result

@api_router.put("/jobs/{job_id}")
async def update_job(job_id: str, updates: Dict[str, Any], token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    updates["updated_at"] = datetime.utcnow()
    
    result = await db.jobs.update_one(
        {"id": job_id},
        {"$set": updates}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {"message": "Job updated"}

@api_router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, token: Dict = Depends(verify_token)):
    if token.get("type") not in ["admin", "masjid"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.jobs.delete_one({"id": job_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {"message": "Job deleted"}

# ============== JOB PROFILES ENDPOINTS ==============

@api_router.get("/profiles")
async def get_job_profiles(role: Optional[str] = None):
    query = {"status": "active"}
    if role:
        query["role"] = role
    
    profiles = await db.job_profiles.find(query).sort("created_at", -1).to_list(1000)
    for p in profiles:
        p.pop('_id', None)
    return profiles

@api_router.get("/profiles/{profile_id}")
async def get_job_profile(profile_id: str):
    profile = await db.job_profiles.find_one({"id": profile_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.pop('_id', None)
    return profile

@api_router.post("/profiles")
async def create_job_profile(profile_data: JobProfileCreate):
    profile = JobProfile(**profile_data.dict())
    
    await db.job_profiles.insert_one(profile.dict())
    
    result = profile.dict()
    result.pop('_id', None)
    return result

@api_router.put("/profiles/{profile_id}")
async def update_job_profile(profile_id: str, updates: Dict[str, Any]):
    updates["updated_at"] = datetime.utcnow()
    
    result = await db.job_profiles.update_one(
        {"id": profile_id},
        {"$set": updates}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return {"message": "Profile updated"}

# ============== DONATIONS ENDPOINTS ==============

@api_router.get("/donations")
async def get_donations(masjid_id: Optional[str] = None):
    query = {}
    if masjid_id:
        query["masjid_id"] = masjid_id
    
    donations = await db.donations.find(query).sort("created_at", -1).to_list(1000)
    for d in donations:
        d.pop('_id', None)
    return donations

@api_router.post("/donations")
async def create_donation(donation_data: DonationCreate):
    # Get masjid name
    masjid = await db.masjids.find_one({"id": donation_data.masjid_id})
    if not masjid:
        raise HTTPException(status_code=404, detail="Masjid not found")
    
    donation = Donation(**donation_data.dict())
    donation.masjid_name = masjid["name"]
    
    await db.donations.insert_one(donation.dict())
    
    result = donation.dict()
    result.pop('_id', None)
    return result

# ============== STATS ENDPOINT ==============

@api_router.get("/stats")
async def get_stats(masjid_id: Optional[str] = None):
    if masjid_id:
        # Masjid-specific stats
        nikahs_count = await db.nikahs.count_documents({"masjid_id": masjid_id})
        matrimony_count = await db.matrimony.count_documents({"masjid_id": masjid_id})
        jobs_count = await db.jobs.count_documents({"masjid_id": masjid_id})
        donations_count = await db.donations.count_documents({"masjid_id": masjid_id})
        
        return {
            "nikahs": nikahs_count,
            "matrimony": matrimony_count,
            "jobs": jobs_count,
            "donations": donations_count
        }
    else:
        # Global stats (admin)
        masjids_count = await db.masjids.count_documents({})
        masjids_pending = await db.masjids.count_documents({"status": "pending"})
        masjids_approved = await db.masjids.count_documents({"status": "approved"})
        nikahs_count = await db.nikahs.count_documents({})
        matrimony_count = await db.matrimony.count_documents({})
        jobs_count = await db.jobs.count_documents({})
        profiles_count = await db.job_profiles.count_documents({})
        donations_count = await db.donations.count_documents({})
        
        return {
            "masjids": masjids_count,
            "masjids_pending": masjids_pending,
            "masjids_approved": masjids_approved,
            "nikahs": nikahs_count,
            "matrimony": matrimony_count,
            "jobs": jobs_count,
            "job_profiles": profiles_count,
            "donations": donations_count
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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
