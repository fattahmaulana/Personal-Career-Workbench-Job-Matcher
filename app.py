import os
import json
from typing import Dict, Any, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from backend.models import UserProfile, JobMatch
from backend.matcher import evaluate_fit
from backend.scraper import scrape_linkedin, scrape_jobstreet, scrape_jsearch, deduplicate_jobs
from backend.parser import extract_text_from_pdf, parse_cv_text_to_profile
from backend.db import init_db, add_application, get_applications, update_application, delete_application

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_PATH = os.path.join(BASE_DIR, "profile.json")
MATCHES_PATH = os.path.join(BASE_DIR, "job_matches.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Inisialisasi Database
init_db()

app = FastAPI(title="Job Search & Auto-Apply Pribadi", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

# Helper I/O
def load_profile() -> Dict[str, Any]:
    if os.path.exists(PROFILE_PATH):
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Default initial state
    return {
        "personal": {
            "name": "",
            "email": "",
            "phone": "",
            "location": "Indonesia",
            "links": []
        },
        "target_role": "Backend Developer",
        "preferences": {
            "locations": ["Indonesia", "Remote"],
            "work_type": "remote",
            "salary_expectation": ""
        },
        "deal_breakers": [
            "Wajib lembur tanpa kompensasi",
            "Onsite penuh jika posisi remote"
        ],
        "languages": [
            {"language": "Indonesian", "level": "native"},
            {"language": "English", "level": "conversational"}
        ],
        "experience": [],
        "education": [],
        "skills": {
            "technical": ["Python", "FastAPI", "SQL", "Git"],
            "soft": ["Problem Solving", "Komunikasi"]
        },
        "certifications": []
    }

def save_profile_file(data: Dict[str, Any]):
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_matches() -> List[Dict[str, Any]]:
    if os.path.exists(MATCHES_PATH):
        try:
            with open(MATCHES_PATH, "r", encoding="utf-8") as f:
                content = json.load(f)
                return content.get("matches", [])
        except Exception:
            return []
    return []

def save_matches_file(matches: List[Dict[str, Any]]):
    with open(MATCHES_PATH, "w", encoding="utf-8") as f:
        json.dump({"matches": matches}, f, indent=2, ensure_ascii=False)

# Routes
@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Web App Ready. Static frontend loading...</h1>"

@app.get("/api/profile")
def get_profile():
    return load_profile()

@app.post("/api/profile")
def update_profile(profile_data: Dict[str, Any] = Body(...)):
    try:
        # Validasi pydantic
        validated = UserProfile(**profile_data)
        # Validasi field wajib
        if not validated.personal.name.strip():
            raise HTTPException(status_code=400, detail="Nama wajib diisi.")
        if not validated.personal.email.strip():
            raise HTTPException(status_code=400, detail="Email wajib diisi.")
        if not validated.target_role.strip():
            raise HTTPException(status_code=400, detail="Target Role wajib diisi.")

        save_profile_file(validated.model_dump())
        return {"status": "ok", "message": "Profil berhasil disimpan ke profile.json", "profile": validated.model_dump()}
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

@app.post("/api/profile/upload-cv")
async def upload_cv_pdf(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Format file harus PDF (.pdf).")
    try:
        contents = await file.read()
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Ukuran file terlalu besar (maksimal 10 MB).")
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="File PDF kosong (0 byte).")

        text = extract_text_from_pdf(contents)
        if not text.strip():
            raise HTTPException(
                status_code=400,
                detail="Tidak ada layer teks yang terbaca dari PDF ini (biasanya terjadi jika CV berupa gambar hasil scan/Canva flat image tanpa selectable text). Silakan gunakan tombol 'Paste Teks CV' di sebelah untuk menempelkan isi CV."
            )

        draft = parse_cv_text_to_profile(text)
        return {"status": "ok", "extracted_text_preview": text[:500], "draft_profile": draft}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses file PDF: {str(e)}")

@app.post("/api/profile/parse-text")
def parse_raw_text(payload: Dict[str, str] = Body(...)):
    raw_text = payload.get("text", "")
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="Teks CV tidak boleh kosong.")
    draft = parse_cv_text_to_profile(raw_text)
    return {"status": "ok", "draft_profile": draft}

@app.post("/api/scrape")
def trigger_scrape():
    prof_dict = load_profile()
    try:
        profile = UserProfile(**prof_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validasi profil gagal. Lengkapi profil terlebih dahulu di /setup. Error: {e}")

    keywords = profile.target_role or "Software Engineer"
    location = profile.preferences.locations[0] if profile.preferences.locations else "Indonesia"

    # 1. Scrape LinkedIn guest
    linkedin_jobs = scrape_linkedin(keywords=keywords, location=location, max_results=15)

    # 2. Scrape Jobstreet
    jobstreet_res = scrape_jobstreet(keywords=keywords, location=location, max_results=10)
    jobstreet_jobs = jobstreet_res.get("jobs", [])

    # 3. Scrape JSearch (Glints, Jobstreet, Indeed, LinkedIn dll via RapidAPI)
    rapid_key = os.environ.get("RAPIDAPI_KEY", "")
    jsearch_jobs = scrape_jsearch(keywords=keywords, location=location, api_key=rapid_key, max_results=15) if rapid_key else []

    # Gabung dan deduplikasi
    all_raw = linkedin_jobs + jobstreet_jobs + jsearch_jobs
    unique_raw = deduplicate_jobs(all_raw)

    # 3. Evaluasi Fit & Hard Gate untuk setiap lowongan
    matched_results = []
    for raw_job in unique_raw:
        match_obj = evaluate_fit(profile, raw_job)
        matched_results.append(match_obj.model_dump())

    # Urutkan berdasarkan skor fit tertinggi (non-rejected di atas)
    matched_results.sort(key=lambda x: (not x["rejected"], x["fit_score"]), reverse=True)

    # Simpan ke job_matches.json
    save_matches_file(matched_results)

    return {
        "status": "ok",
        "total_scraped": len(all_raw),
        "total_unique": len(unique_raw),
        "sources": {
            "linkedin_count": len(linkedin_jobs),
            "jobstreet_status": jobstreet_res.get("status"),
            "jobstreet_message": jobstreet_res.get("message"),
            "jobstreet_count": len(jobstreet_jobs),
            "jsearch_count": len(jsearch_jobs)
        },
        "matches": matched_results
    }

@app.get("/api/matches")
def get_job_matches():
    return load_matches()

@app.post("/api/jobs/manual")
def add_manual_job(payload: Dict[str, Any] = Body(...)):
    """Tambah lowongan manual (misal copy-paste dari Jobstreet yang diblokir atau situs lain)."""
    prof_dict = load_profile()
    profile = UserProfile(**prof_dict)

    job_data = {
        "title": payload.get("title", "Posisi Baru"),
        "company": payload.get("company", "Perusahaan"),
        "location": payload.get("location", "Indonesia"),
        "source": payload.get("source", "manual"),
        "url": payload.get("url", ""),
        "description": payload.get("description", "")
    }

    match_obj = evaluate_fit(profile, job_data)
    match_dict = match_obj.model_dump()

    matches = load_matches()
    matches.insert(0, match_dict)
    save_matches_file(matches)

    return {"status": "ok", "match": match_dict}

@app.post("/api/apply/preview")
def preview_application(payload: Dict[str, Any] = Body(...)):
    """Mengevaluasi detail kecocokan & gaps untuk satu lowongan spesifik."""
    prof_dict = load_profile()
    profile = UserProfile(**prof_dict)

    match_obj = evaluate_fit(profile, payload)
    return {
        "job": payload,
        "evaluation": match_obj.model_dump(),
        "ready_to_draft": not match_obj.rejected
    }

@app.post("/api/apply/track")
def track_application(payload: Dict[str, Any] = Body(...)):
    """Simpan lowongan ke applications_tracker SQLite."""
    app_id = add_application(payload)
    return {"status": "ok", "id": app_id, "message": "Lamaran berhasil dicatat ke tracker."}

@app.get("/api/applications")
def list_applications():
    return get_applications()

@app.patch("/api/applications/{app_id}")
def update_app_status(app_id: int, payload: Dict[str, Any] = Body(...)):
    ok = update_application(app_id, payload)
    if not ok:
        raise HTTPException(status_code=400, detail="Update gagal atau ID tidak ditemukan.")
    return {"status": "ok", "message": "Data lamaran berhasil diperbarui."}

@app.delete("/api/applications/{app_id}")
def remove_application(app_id: int):
    ok = delete_application(app_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Lamaran tidak ditemukan atau sudah dihapus.")
    return {"status": "ok", "message": "Lamaran berhasil dihapus."}

@app.post("/api/generate-cover-letter")
def generate_cover_letter(payload: Dict[str, Any] = Body(...)):
    """Generator Cover Letter gratis & offline berbasis data profil dan info lowongan."""
    prof = load_profile()
    name = prof.get("personal", {}).get("name", "Pelamar")
    email = prof.get("personal", {}).get("email", "")
    phone = prof.get("personal", {}).get("phone", "")
    skills = ", ".join(prof.get("skills", {}).get("technical", [])[:5]) or "pengembangan software"

    company = payload.get("company", "Bapak/Ibu HRD")
    position = payload.get("title", prof.get("target_role", "Software Engineer"))
    lang = payload.get("lang", "id")

    if lang == "en":
        letter = f"""Dear Hiring Team at {company},

I am writing to express my strong interest in the {position} position at {company}. With a proven background in {skills}, I am confident in my ability to make an immediate, positive contribution to your engineering team.

My technical expertise aligns closely with modern software development practices, problem-solving, and efficient system architecture. I am particularly drawn to {company} due to your work and commitment to quality engineering.

Thank you for your time and consideration. I welcome the opportunity to discuss how my skills and background can best support your team's goals.

Sincerely,
{name}
{email} | {phone}"""
    else:
        letter = f"""Yth. Tim Rekrutmen / HRD {company},

Melalui surat ini, saya ingin menyampaikan ketertarikan saya untuk bergabung sebagai {position} di {company}. Berbekal kompetensi dan keahlian di bidang {skills}, saya yakin dapat memberikan kontribusi nyata bagi pencapaian target tim.

Saya terbiasa membangun solusi perangkat lunak yang andal, efisien, dan siap berkembang sesuai kebutuhan bisnis. Saya sangat mengapresiasi reputasi dan dedikasi {company}, dan saya antusias untuk membawa etos kerja serta keterampilan teknis saya ke dalam tim Anda.

Terima kasih atas waktu dan kesempatan yang diberikan. Saya sangat menantikan kesempatan wawancara untuk mendiskusikan kualifikasi saya lebih lanjut.

Hormat saya,
{name}
{email} | {phone}"""

    return {"status": "ok", "cover_letter": letter}

