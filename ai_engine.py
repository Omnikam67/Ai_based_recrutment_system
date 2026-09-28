import re
from db import get_db
from ml_model import predict_candidate

# Simple explainable NLP layer for a DBMS mini-project.
# It extracts skills from resume/JD text and calculates TF-IDF-style
# text similarity when scikit-learn is installed.

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

def normalize(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()

def get_candidate(candidate_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM candidates WHERE candidate_id=%s", (candidate_id,))
    row = cur.fetchone()
    cur.close(); db.close()
    return row

def get_job(job_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM jobs WHERE job_id=%s", (job_id,))
    row = cur.fetchone()
    cur.execute("""
        SELECT s.skill_id, s.skill_name, js.required_level, js.importance
        FROM job_skills js JOIN skills s ON s.skill_id=js.skill_id
        WHERE js.job_id=%s
    """, (job_id,))
    skills = cur.fetchall()
    cur.close(); db.close()
    return row, skills

def extract_skills(text, known_skills):
    text = normalize(text)
    found = []
    for skill in known_skills:
        if re.search(r"(?<!\w)" + re.escape(skill.lower()) + r"(?!\w)", text):
            found.append(skill)
    return sorted(set(found))

def text_similarity(a, b):
    if not a or not b:
        return 0.0
    if SKLEARN_OK:
        vec = TfidfVectorizer(stop_words="english")
        matrix = vec.fit_transform([a, b])
        return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    # Fallback: token Jaccard similarity
    A, B = set(normalize(a).split()), set(normalize(b).split())
    return len(A & B) / max(1, len(A | B))

def analyze_candidate_for_job(candidate_id, job_id):
    candidate = get_candidate(candidate_id)
    job, required = get_job(job_id)
    if not candidate or not job:
        return {"error": "Candidate or job not found."}

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT s.skill_name, cs.proficiency FROM candidate_skills cs JOIN skills s ON s.skill_id=cs.skill_id WHERE cs.candidate_id=%s", (candidate_id,))
    existing = cur.fetchall()
    cur.close(); db.close()

    known = [x["skill_name"] for x in required]
    resume_text = candidate.get("resume_text", "")
    extracted = extract_skills(resume_text, known)

    # Existing skills from DB are also considered.
    existing_names = {x["skill_name"].lower() for x in existing}
    existing_proficiency = {
        x["skill_name"].lower(): x["proficiency"] for x in existing
    }
    candidate_names = existing_names | {x.lower() for x in extracted}

    matched = [
        {**x, "candidate_level": existing_proficiency.get(x["skill_name"].lower())}
        for x in required if x["skill_name"].lower() in candidate_names
    ]
    missing = [x for x in required if x["skill_name"].lower() not in candidate_names]
    proficiency_rank = {"Beginner": 1, "Intermediate": 2, "Advanced": 3, "Expert": 4}
    level_gaps = [
        {
            **skill,
            "candidate_level": skill["candidate_level"],
            "required_level": skill.get("required_level") or "Intermediate",
        }
        for skill in matched
        if skill["candidate_level"] in proficiency_rank
        and (skill.get("required_level") or "Intermediate") in proficiency_rank
        and proficiency_rank[skill["candidate_level"]]
        < proficiency_rank[skill.get("required_level") or "Intermediate"]
    ]

    skill_score = (len(matched) / max(1, len(required))) * 100
    req_exp = float(job.get("min_experience") or 0)
    exp = float(candidate.get("experience_years") or 0)
    experience_score = 100 if req_exp == 0 else min(100, (exp / req_exp) * 100)

    education_score = 100 if candidate.get("education") else 50
    similarity = text_similarity(resume_text, job.get("description", "")) * 100

    overall = (
        skill_score * 0.60 +
        experience_score * 0.20 +
        education_score * 0.10 +
        similarity * 0.10
    )

    # Persist ranking and skill gaps to MySQL.
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("""
            INSERT INTO candidate_scores
            (candidate_id, job_id, skill_score, experience_score, education_score, nlp_similarity, overall_score)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
            skill_score=VALUES(skill_score),
            experience_score=VALUES(experience_score),
            education_score=VALUES(education_score),
            nlp_similarity=VALUES(nlp_similarity),
            overall_score=VALUES(overall_score)
        """, (candidate_id, job_id, skill_score, experience_score, education_score, similarity, overall))

        cur.execute("DELETE FROM skill_gaps WHERE candidate_id=%s AND job_id=%s", (candidate_id, job_id))
        for x in missing:
            cur.execute("""
                INSERT INTO skill_gaps(candidate_id, job_id, skill_id, required_level, candidate_level, gap_level)
                VALUES (%s,%s,%s,%s,'None','High')
            """, (candidate_id, job_id, x["skill_id"], x["required_level"]))
        for x in level_gaps:
            cur.execute("""
                INSERT INTO skill_gaps(candidate_id, job_id, skill_id, required_level, candidate_level, gap_level)
                VALUES (%s,%s,%s,%s,%s,'Medium')
            """, (candidate_id, job_id, x["skill_id"], x["required_level"], x["candidate_level"]))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close(); db.close()

    ml_prediction = predict_candidate(
        experience=exp,
        skills_count=len(matched),
        skill_match=skill_score,
        education_score=education_score,
        interview_score=min(100, max(0, (overall + similarity) / 2))
    )

    return {
        "candidate": candidate,
        "job": job,
        "matched": matched,
        "missing": missing,
        "level_gaps": level_gaps,
        "skill_score": round(skill_score, 2),
        "experience_score": round(experience_score, 2),
        "education_score": round(education_score, 2),
        "nlp_similarity": round(similarity, 2),
        "overall_score": round(overall, 2),
        "ml_prediction": ml_prediction
    }
