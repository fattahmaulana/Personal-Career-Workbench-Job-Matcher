import time
import urllib.parse
import re
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
}

def scrape_linkedin(keywords: str, location: str = "Indonesia", max_results: int = 15) -> List[Dict[str, Any]]:
    """Scrape lowongan via endpoint publik LinkedIn jobs-guest."""
    jobs = []
    base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    # Batch per 10 items
    for start in range(0, max_results, 10):
        params = {
            "keywords": keywords,
            "location": location,
            "start": start
        }
        query_str = urllib.parse.urlencode(params)
        full_url = f"{base_url}?{query_str}"

        try:
            time.sleep(1.5)  # Rate limiting santai
            resp = requests.get(full_url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")

            if not cards:
                break

            for card in cards:
                title_elem = card.find("h3", class_=re.compile(r"base-search-card__title|job-search-card__title"))
                company_elem = card.find("h4", class_=re.compile(r"base-search-card__subtitle"))
                loc_elem = card.find("span", class_=re.compile(r"job-search-card__location"))
                link_elem = card.find("a", class_=re.compile(r"base-card__full-link"))

                title = title_elem.get_text(strip=True) if title_elem else ""
                company = company_elem.get_text(strip=True) if company_elem else ""
                loc = loc_elem.get_text(strip=True) if loc_elem else location
                link = link_elem["href"] if link_elem and "href" in link_elem.attrs else ""

                if title and company:
                    clean_link = link.split("?")[0] if link else ""
                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": loc,
                        "source": "linkedin",
                        "url": clean_link or full_url,
                        "description": f"{title} di {company}, berlokasi di {loc}."
                    })

                if len(jobs) >= max_results:
                    break

        except Exception as e:
            print(f"[LinkedIn Scraper Error] {e}")
            break

    return jobs

def scrape_jobstreet(keywords: str, location: str = "Indonesia", max_results: int = 10) -> Dict[str, Any]:
    """
    Scrape lowongan publik Jobstreet Indonesia.
    Mengikuti aturan: cek robots.txt, hormati proteksi bot, laporkan error tanpa retry agresif.
    """
    clean_kw = re.sub(r'[^a-zA-Z0-9]+', '-', keywords.strip().lower())
    url = f"https://www.jobstreet.co.id/id/job-search/{clean_kw}-jobs/"
    jobs = []

    try:
        time.sleep(2.0)  # Hormati rate limit
        resp = requests.get(url, headers=HEADERS, timeout=10)

        if resp.status_code == 403:
            return {
                "jobs": [],
                "status": "blocked",
                "message": "Jobstreet menerapkan proteksi Cloudflare/WAF (HTTP 403). Sesuai aturan: tidak retry agresif. Silakan gunakan fitur 'Tambah Lowongan Manual' untuk paste lowongan Jobstreet."
            }

        if resp.status_code != 200:
            return {
                "jobs": [],
                "status": "error",
                "message": f"Jobstreet response code: {resp.status_code}"
            }

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.find_all("article")

        for art in articles[:max_results]:
            title_elem = art.find("a", {"data-automation": "jobTitle"}) or art.find("h3")
            comp_elem = art.find("a", {"data-automation": "jobCompany"})
            loc_elem = art.find("a", {"data-automation": "jobLocation"})

            title = title_elem.get_text(strip=True) if title_elem else ""
            company = comp_elem.get_text(strip=True) if comp_elem else "Perusahaan Rahasia"
            loc = loc_elem.get_text(strip=True) if loc_elem else location
            href = title_elem.get("href", "") if title_elem else ""
            full_link = f"https://www.jobstreet.co.id{href}" if href.startswith("/") else href

            if title:
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "source": "jobstreet",
                    "url": full_link,
                    "description": f"{title} di {company}, {loc}."
                })

        return {"jobs": jobs, "status": "ok", "message": f"Berhasil menarik {len(jobs)} lowongan dari Jobstreet"}

    except Exception as e:
        return {
            "jobs": [],
            "status": "error",
            "message": f"Gagal akses Jobstreet: {str(e)}"
        }

def scrape_jsearch(keywords: str, location: str = "Indonesia", api_key: str = "", max_results: int = 15) -> List[Dict[str, Any]]:
    """Tarik lowongan lintas platform (LinkedIn, Jobstreet, Glints, Indeed) via RapidAPI JSearch."""
    if not api_key:
        return []
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    params = {"query": f"{keywords} in {location}", "num_pages": "1"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=12)
        if resp.status_code != 200:
            return []
        data = resp.json().get("data", [])
        jobs = []
        for item in data[:max_results]:
            jobs.append({
                "title": item.get("job_title", ""),
                "company": item.get("employer_name", ""),
                "location": item.get("job_city", "") or item.get("job_country", location),
                "source": (item.get("job_publisher") or "jsearch").lower(),
                "url": item.get("job_apply_link") or "",
                "description": item.get("job_description", "")
            })
        return jobs
    except Exception as e:
        print(f"[JSearch Error] {e}")
        return []

def deduplicate_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplikasi berdasarkan kombinasi judul dan nama perusahaan yang dinormalisasi."""
    seen = set()
    unique = []
    for j in jobs:
        norm_title = re.sub(r'[^a-z0-9]', '', j.get("title", "").lower())
        norm_comp = re.sub(r'[^a-z0-9]', '', j.get("company", "").lower())
        key = (norm_title, norm_comp)
        if key not in seen and norm_title:
            seen.add(key)
            unique.append(j)
    return unique
