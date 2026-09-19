import re
import io
from typing import Dict, Any, List
from pypdf import PdfReader

COMMON_TECH = [
    "python", "javascript", "typescript", "react", "vue", "angular", "node.js", "nodejs",
    "fastapi", "django", "flask", "docker", "kubernetes", "aws", "gcp", "azure", "sql",
    "postgresql", "mysql", "mongodb", "redis", "git", "linux", "html", "css", "tailwind",
    "graphql", "rest api", "ci/cd", "golang", "java", "c++", "c#"
]

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Ekstrak teks polos dari file PDF menggunakan pypdf dengan pengamanan error stream."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text_pages = []
        for page in reader.pages:
            try:
                txt = page.extract_text()
                if txt and txt.strip():
                    text_pages.append(txt.strip())
            except Exception:
                continue
        return "\n\n".join(text_pages)
    except Exception as e:
        print(f"[PDF Extract Warning] {e}")
        return ""

def parse_cv_text_to_profile(text: str) -> Dict[str, Any]:
    """Parsing teks CV menjadi draft UserProfile."""
    # 1. Email
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    email = email_match.group(0) if email_match else ""

    # 2. Phone
    phone_match = re.search(r'(\+?62|08)[0-9\- ]{8,14}', text)
    phone = phone_match.group(0).strip() if phone_match else ""

    # 3. Links
    links = []
    for link_match in re.finditer(r'(https?://[^\s]+|linkedin\.com/in/[^\s]+|github\.com/[^\s]+)', text):
        links.append(link_match.group(0))

    # 4. Name: baris pertama non-empty biasanya nama
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    name = lines[0] if lines and len(lines[0]) < 50 else ""

    # 5. Skills
    text_lower = text.lower()
    found_tech = []
    for skill in COMMON_TECH:
        if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
            found_tech.append(skill)

    # 6. Languages
    languages = []
    if "english" in text_lower or "inggris" in text_lower:
        languages.append({"language": "English", "level": "conversational"})
    if "indonesia" in text_lower or not languages:
        languages.append({"language": "Indonesian", "level": "native"})

    # 7. Target role
    target_role = ""
    for r in ["Software Engineer", "Backend Developer", "Fullstack Developer", "Frontend Developer", "Data Scientist", "DevOps Engineer"]:
        if r.lower() in text_lower:
            target_role = r
            break
    if not target_role and lines and len(lines) > 1 and len(lines[1]) < 40:
        target_role = lines[1]

    # Return draft profile
    return {
        "personal": {
            "name": name,
            "email": email,
            "phone": phone,
            "location": "Indonesia",
            "links": list(set(links))[:5]
        },
        "target_role": target_role or "Software Engineer",
        "preferences": {
            "locations": ["Jakarta", "Remote Indonesia"],
            "work_type": "remote",
            "salary_expectation": ""
        },
        "deal_breakers": [
            "Tidak mau lembur rutin",
            "Harus lingkungan kerja etis"
        ],
        "languages": languages,
        "experience": [
            {
                "company": "Perusahaan Terakhir",
                "position": target_role or "Software Developer",
                "duration": "2022 - Sekarang",
                "responsibilities": ["Mengembangkan backend API", "Optimasi query database"]
            }
        ],
        "education": [
            {
                "institution": "Universitas",
                "degree": "S1 / Sarjana",
                "field": "Teknik Informatika / Ilmu Komputer",
                "year": "2022"
            }
        ],
        "skills": {
            "technical": found_tech if found_tech else ["Python", "FastAPI", "PostgreSQL"],
            "soft": ["Problem Solving", "Komunikasi Tim", "Manajemen Waktu"]
        },
        "certifications": []
    }
