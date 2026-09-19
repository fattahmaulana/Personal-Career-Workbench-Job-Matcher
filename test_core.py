from backend.models import UserProfile, PersonalInfo, Preferences, Language, Skills, Experience
from backend.matcher import evaluate_fit
from backend.scraper import deduplicate_jobs, scrape_jsearch
from backend.db import init_db, add_application, get_applications, update_application, delete_application

def test_all():
    print("Menjalankan test fondasi...")

    # 1. Test Setup Profile
    profile = UserProfile(
        personal=PersonalInfo(name="Budi Santoso", email="budi@example.com", phone="08123456789"),
        target_role="Backend Developer",
        preferences=Preferences(work_type="remote", locations=["Indonesia"]),
        deal_breakers=["Wajib lembur"],
        languages=[
            Language(language="Indonesian", level="native"),
            Language(language="English", level="basic")
        ],
        skills=Skills(technical=["Python", "FastAPI", "PostgreSQL", "Docker"])
    )
    assert profile.personal.name == "Budi Santoso"
    assert "Python" in profile.skills.technical

    # 2. Test Gate Keras: Bahasa Asing yang Sama Sekali Tidak Dikuasai
    job_mandarin = {
        "title": "Backend Dev",
        "company": "Tech Corp",
        "location": "Jakarta",
        "description": "Requirement: Fluent in Mandarin is mandatory. Python, SQL."
    }
    match_mandarin = evaluate_fit(profile, job_mandarin)
    assert match_mandarin.rejected is True, "Harus auto-reject karena butuh Mandarin"
    assert "mandarin" in match_mandarin.rejection_reason.lower()

    # 3. Test Gate Keras: Deal Breaker
    job_overtime = {
        "title": "Backend Dev",
        "company": "Crunch Corp",
        "location": "Jakarta",
        "description": "Posisi Backend, wajib lembur setiap weekend."
    }
    match_overtime = evaluate_fit(profile, job_overtime)
    assert match_overtime.rejected is True, "Harus auto-reject karena wajib lembur"

    # 4. Test Warning Level Bahasa Lebih Tinggi (bukan auto-reject)
    job_eng_fluent = {
        "title": "Python Backend Developer",
        "company": "Global Remote",
        "location": "Remote",
        "description": "Requirements: Fluent English, Python, FastAPI, PostgreSQL, remote friendly."
    }
    match_eng = evaluate_fit(profile, job_eng_fluent)
    assert match_eng.rejected is False, "Level bahasa lebih tinggi tidak boleh auto-reject"
    assert len(match_eng.warnings) > 0, "Harus ada warning bahasa"
    assert match_eng.fit_score > 60, f"Fit score harus tinggi, didapat: {match_eng.fit_score}"

    # 5. Test Deduplikasi
    raw_jobs = [
        {"title": "Python Developer", "company": "ABC Corp", "location": "Jakarta"},
        {"title": "python developer", "company": "abc corp", "location": "Jakarta"},
        {"title": "Backend Engineer", "company": "XYZ Ltd", "location": "Remote"}
    ]
    unique = deduplicate_jobs(raw_jobs)
    assert len(unique) == 2, f"Deduplikasi harus menghasilkan 2 item, didapat: {len(unique)}"

    # 6. Test JSearch fallback
    assert scrape_jsearch("dev", "indonesia", api_key="") == []

    # 7. Test SQLite Tracker
    init_db()
    app_id = add_application({
        "title": "Python Dev",
        "company": "Global Remote",
        "source": "linkedin",
        "fit_score": 85,
        "status": "draft"
    })
    assert app_id > 0
    ok = update_application(app_id, {"status": "interview"})
    assert ok is True
    all_apps = get_applications()
    assert any(a["id"] == app_id and a["status"] == "interview" for a in all_apps)

    # 8. Test Delete Application
    del_ok = delete_application(app_id)
    assert del_ok is True
    all_apps_after = get_applications()
    assert not any(a["id"] == app_id for a in all_apps_after)

    print("Semua test lolos! (Fondasi profil, scraping parser, gate keras, scoring, SQLite beres)")

if __name__ == "__main__":
    test_all()
