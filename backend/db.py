import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "applications.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        url TEXT,
        source TEXT,
        fit_score INTEGER DEFAULT 0,
        status TEXT DEFAULT 'draft',
        applied_date TEXT,
        cv_path TEXT,
        cover_letter_path TEXT,
        interview_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

def add_application(app_data: Dict[str, Any]) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO applications (title, company, url, source, fit_score, status, applied_date, cv_path, cover_letter_path, interview_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        app_data.get("title", ""),
        app_data.get("company", ""),
        app_data.get("url", ""),
        app_data.get("source", "manual"),
        app_data.get("fit_score", 0),
        app_data.get("status", "draft"),
        app_data.get("applied_date", datetime.now().strftime("%Y-%m-%d")),
        app_data.get("cv_path", ""),
        app_data.get("cover_letter_path", ""),
        app_data.get("interview_notes", "")
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def get_applications() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM applications ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_application(app_id: int, updates: Dict[str, Any]) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    allowed_fields = ["status", "applied_date", "cv_path", "cover_letter_path", "interview_notes"]
    set_clauses = []
    values = []

    for k, v in updates.items():
        if k in allowed_fields:
            set_clauses.append(f"{k} = ?")
            values.append(v)

    if not set_clauses:
        conn.close()
        return False

    values.append(app_id)
    query = f"UPDATE applications SET {', '.join(set_clauses)} WHERE id = ?"
    cursor.execute(query, values)
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0

def delete_application(app_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0

