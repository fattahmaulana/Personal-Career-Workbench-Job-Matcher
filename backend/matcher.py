import re
from typing import Tuple, List, Dict, Any
from .models import UserProfile, JobMatch

LEVEL_HIERARCHY = {
    "basic": 1,
    "beginner": 1,
    "dasar": 1,
    "conversational": 2,
    "menengah": 2,
    "intermediate": 2,
    "professional": 3,
    "profesional": 3,
    "fluent": 4,
    "lancar": 4,
    "native": 5,
    "fasih": 5
}

COMMON_LANGUAGES = [
    "english", "inggris", "indonesia", "mandarin", "japanese",
    "jepang", "korean", "korea", "german", "jerman", "french", "prancis"
]

def extract_language_requirements(text: str) -> List[Tuple[str, str]]:
    """Detect language and required level from job text."""
    text_lower = text.lower()
    results = []

    for lang in COMMON_LANGUAGES:
        if re.search(r'\b' + lang + r'\b', text_lower):
            # Check proximity to level indicators
            std_lang = "english" if lang in ["english", "inggris"] else \
                       "indonesian" if lang in ["indonesia"] else \
                       "mandarin" if lang in ["mandarin"] else \
                       "japanese" if lang in ["japanese", "jepang"] else lang

            level = "conversational"
            if re.search(r'(fluent|native|fasih|lancar|proficient)\s+(in\s+)?' + lang, text_lower) or \
               re.search(lang + r'\s+(fluent|native|fasih|lancar|proficient)', text_lower):
                level = "fluent"
            elif re.search(r'(basic|dasar)\s+' + lang, text_lower) or re.search(lang + r'\s+(basic|dasar)', text_lower):
                level = "basic"
            results.append((std_lang, level))

    return results

def check_deal_breakers(profile: UserProfile, job_text: str) -> Tuple[bool, str]:
    """Gate keras: jika deal-breaker terlanggar, return (True, reason)."""
    text_lower = job_text.lower()

    # Check user-defined deal-breakers
    for db in profile.deal_breakers:
        db_clean = db.strip().lower()
        if not db_clean:
            continue

        # Contoh deal-breaker: "tidak mau lembur", "no overtime"
        if ("lembur" in db_clean or "overtime" in db_clean) and ("overtime required" in text_lower or "wajib lembur" in text_lower):
            return True, f"Deal-breaker terlanggar: Lowongan membutuhkan lembur ('{db}')"

        # Contoh deal-breaker: "harus remote"
        if ("harus remote" in db_clean or "must be remote" in db_clean or "remote only" in db_clean):
            if "onsite" in text_lower and "remote" not in text_lower:
                return True, "Deal-breaker terlanggar: Lowongan onsite, user hanya ingin remote"

        # Direct phrase match
        if len(db_clean) > 3 and db_clean in text_lower:
            return True, f"Deal-breaker terlanggar: {db}"

    # Preferensi work_type keras
    if profile.preferences.work_type.lower() == "remote":
        if re.search(r'\b(full[- ]?time onsite|100% onsite|wfo only)\b', text_lower):
            return True, "Deal-breaker terlanggar: Lowongan 100% Onsite (WFO), preferensi remote"

    return False, ""

def evaluate_fit(profile: UserProfile, job: Dict[str, Any]) -> JobMatch:
    """Evaluasi fit score 0-100 dan gate keras."""
    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")
    source = job.get("source", "linkedin")
    url = job.get("url", "")
    desc = job.get("description", "")
    full_text = f"{title} {desc} {location}".lower()

    gaps = []
    warnings = []

    # 1. Gate Keras: Deal Breakers
    is_deal_broken, db_reason = check_deal_breakers(profile, full_text)
    if is_deal_broken:
        return JobMatch(
            title=title, company=company, location=location, source=source,
            url=url, description=desc, fit_score=0,
            reason="Ditolak otomatis oleh filter Deal-Breaker",
            rejected=True, rejection_reason=db_reason
        )

    # 2. Gate Keras: Bahasa
    user_langs = {l.language.lower(): l.level.lower() for l in profile.languages}
    # Default: Indonesia assumed if not stated
    if "indonesia" not in user_langs and "indonesian" not in user_langs:
        user_langs["indonesian"] = "native"

    req_langs = extract_language_requirements(full_text)
    for r_lang, r_lvl in req_langs:
        matched_user_lvl = None
        for u_l, u_lvl in user_langs.items():
            if r_lang in u_l or u_l in r_lang:
                matched_user_lvl = u_lvl
                break

        if not matched_user_lvl:
            return JobMatch(
                title=title, company=company, location=location, source=source,
                url=url, description=desc, fit_score=0,
                reason=f"Ditolak otomatis: Lowongan mensyaratkan bahasa '{r_lang}' yang tidak dikuasai",
                rejected=True, rejection_reason=f"Bahasa {r_lang} tidak dikuasai sama sekali"
            )
        else:
            r_val = LEVEL_HIERARCHY.get(r_lvl, 2)
            u_val = LEVEL_HIERARCHY.get(matched_user_lvl, 2)
            if r_val > u_val:
                warnings.append(f"Level bahasa {r_lang} yang diminta ({r_lvl}) lebih tinggi dari profil ({matched_user_lvl})")

    # 3. Komponen Penilaian (0 - 100)
    # A. Technical skills: 40%
    matched_tech = []
    missing_tech = []
    user_tech = [s.lower().strip() for s in profile.skills.technical if s.strip()]

    if user_tech:
        for skill in user_tech:
            # Word boundary check
            if re.search(r'\b' + re.escape(skill) + r'\b', full_text):
                matched_tech.append(skill)

        tech_score = (len(matched_tech) / max(1, len(user_tech))) * 100
        # Cap tech score at 100
        tech_score = min(100.0, tech_score * 2.0)  # Boost: matching 50% user skills is great
    else:
        tech_score = 50.0

    # Cari keyword penting di deskripsi yang mungkin belum dimiliki
    common_dev_keywords = ["docker", "kubernetes", "aws", "gcp", "azure", "postgresql", "react", "vue", "fastapi", "django", "node", "typescript", "golang"]
    for kw in common_dev_keywords:
        if kw in full_text and kw not in user_tech and kw not in matched_tech:
            missing_tech.append(kw)
    if missing_tech:
        gaps.append(f"Skill lowongan belum ada di profil: {', '.join(missing_tech[:4])}")

    # B. Pengalaman & Level Jabatan: 25%
    exp_score = 50.0
    role_lower = profile.target_role.lower()
    if role_lower and role_lower in full_text:
        exp_score = 100.0
    elif any(word in full_text for word in role_lower.split() if len(word) > 3):
        exp_score = 80.0
    else:
        exp_score = 40.0

    # Level seniority check
    is_senior_job = bool(re.search(r'\b(senior|lead|principal|head|manager)\b', full_text))
    user_years = len(profile.experience) * 2  # Estimasi kasar
    if is_senior_job and user_years < 3:
        warnings.append("Lowongan level Senior/Lead, pengalaman profil mungkin di bawah rata-rata")
        exp_score = max(20.0, exp_score - 30)

    # C. Lokasi & Tipe Kerja: 15%
    loc_score = 50.0
    pref_type = profile.preferences.work_type.lower()
    if "remote" in full_text and pref_type in ["remote", "any", "hybrid"]:
        loc_score = 100.0
    elif "hybrid" in full_text and pref_type in ["hybrid", "any"]:
        loc_score = 90.0
    else:
        pref_locs = [l.lower() for l in profile.preferences.locations]
        if any(pl in full_text for pl in pref_locs if pl):
            loc_score = 85.0
        elif pref_type == "remote" and "remote" not in full_text:
            loc_score = 30.0
            gaps.append("Lowongan tidak secara spesifik menyebut opsi Remote")

    # D. Industri / Domain: 10%
    ind_score = 70.0  # Default neutral baseline

    # E. Bahasa: 10%
    lang_score = 100.0 if not warnings else 70.0

    # Kalkulasi Final
    final_score = int(
        (tech_score * 0.40) +
        (exp_score * 0.25) +
        (loc_score * 0.15) +
        (ind_score * 0.10) +
        (lang_score * 0.10)
    )
    final_score = max(0, min(100, final_score))

    reason_parts = []
    if matched_tech:
        reason_parts.append(f"Skill cocok: {', '.join(matched_tech[:3])}")
    if "remote" in full_text:
        reason_parts.append("Dukungan remote")
    reason = " | ".join(reason_parts) if reason_parts else "Kecocokan umum dengan profil"

    return JobMatch(
        title=title,
        company=company,
        location=location,
        source=source,
        url=url,
        description=desc,
        fit_score=final_score,
        reason=reason,
        gaps=gaps,
        warnings=warnings,
        rejected=False,
        rejection_reason="",
        score_breakdown={
            "tech": round(tech_score, 1),
            "experience": round(exp_score, 1),
            "location_work_type": round(loc_score, 1),
            "industry": round(ind_score, 1),
            "language": round(lang_score, 1)
        }
    )
