from flask import Flask, render_template, request, redirect, url_for, flash, session
from db import get_db
from ai_engine import analyze_candidate_for_job, extract_skills
from ml_model import predict_candidate

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

HR_ROUTES = {"dashboard", "candidates", "add_candidate", "jobs", "add_job", "applications", "apply_to_job", "analyze", "rank", "apply"}
USER_ROUTES = {"user_dashboard", "my_applications", "user_apply"}


def is_candidate_role(role):
    return role in {"User", "Candidate"}


@app.before_request
def require_login():
    if request.endpoint in (None, "login", "register", "static"):
        return None
    if request.endpoint == "logout":
        return None
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.endpoint in HR_ROUTES and session.get("user_role") != "HR":
        return redirect(url_for("user_dashboard"))

    if request.endpoint in USER_ROUTES and session.get("user_role") == "HR":
        return redirect(url_for("dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        if session.get("user_role") == "HR":
            return redirect(url_for("dashboard"))
        return redirect(url_for("user_dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "User").strip()

        if not name or not email or not password:
            flash("Please fill in all fields.", "danger")
            return render_template("register.html")

        if role not in {"HR", "User", "Candidate"}:
            flash("Invalid role selected.", "danger")
            return render_template("register.html")

        db = get_db()
        cur = db.cursor(dictionary=True)
        try:
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            existing = cur.fetchone()
            if existing:
                flash("This email is already registered.", "warning")
                return render_template("register.html")

            cur.execute(
                "INSERT INTO users(name, email, password, role) VALUES (%s, %s, %s, %s)",
                (name, email, password, role)
            )
            db.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            db.rollback()
            flash(f"Registration failed: {e}", "danger")
            return render_template("register.html")
        finally:
            cur.close(); db.close()

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        if session.get("user_role") == "HR":
            return redirect(url_for("dashboard"))
        return redirect(url_for("user_dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "HR").strip()

        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s AND role=%s", (email, role))
        user = cur.fetchone()
        cur.close(); db.close()

        if user and user["password"] == password:
            session["user_id"] = user["user_id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]
            flash("Login successful.", "success")
            if user["role"] == "HR":
                return redirect(url_for("dashboard"))
            return redirect(url_for("user_dashboard"))

        flash("Invalid email, password, or role.", "danger")
        return render_template("login.html")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

@app.route("/user-dashboard")
def user_dashboard():
    if not (session.get("user_role") in {"User", "Candidate"}):
        return redirect(url_for("dashboard"))

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM jobs WHERE status='Open' ORDER BY job_id DESC")
    jobs = cur.fetchall()
    cur.close(); db.close()
    return render_template("user_dashboard.html", jobs=jobs)

@app.route("/my-applications")
def my_applications():
    if not (session.get("user_role") in {"User", "Candidate"}):
        return redirect(url_for("dashboard"))

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT a.application_id, a.status, a.application_date, j.job_title, j.company, j.location
        FROM applications a
        JOIN jobs j ON j.job_id = a.job_id
        WHERE a.candidate_id = %s
        ORDER BY a.application_date DESC
    """, (session["user_id"],))
    rows = cur.fetchall()
    cur.close(); db.close()
    return render_template("my_applications.html", applications=rows)

@app.route("/user/apply/<int:job_id>", methods=["POST"])
def user_apply(job_id):
    if not (session.get("user_role") in {"User", "Candidate"}):
        return redirect(url_for("dashboard"))

    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("""
            INSERT INTO applications(candidate_id, job_id, status)
            VALUES (%s, %s, 'Applied')
            ON DUPLICATE KEY UPDATE status='Applied'
        """, (session["user_id"], job_id))
        db.commit()
        flash("Your application was submitted successfully.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Application failed: {e}", "danger")
    finally:
        cur.close(); db.close()

    return redirect(url_for("my_applications"))

@app.route("/")
def dashboard():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) AS total FROM candidates")
    candidates = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM jobs WHERE status='Open'")
    jobs = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM applications")
    applications = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM applications WHERE status='Shortlisted'")
    shortlisted = cur.fetchone()["total"]
    cur.execute("""
        SELECT c.name, j.job_title, cs.overall_score
        FROM candidate_scores cs
        JOIN candidates c ON c.candidate_id = cs.candidate_id
        JOIN jobs j ON j.job_id = cs.job_id
        ORDER BY cs.overall_score DESC
        LIMIT 5
    """)
    top = cur.fetchall()
    cur.close(); db.close()
    return render_template("dashboard.html", candidates=candidates, jobs=jobs,
                           applications=applications, shortlisted=shortlisted, top=top)

@app.route("/candidates")
def candidates():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM candidates ORDER BY candidate_id DESC")
    rows = cur.fetchall()
    cur.close(); db.close()
    return render_template("candidates.html", candidates=rows)

@app.route("/candidates/add", methods=["GET", "POST"])
def add_candidate():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        phone = request.form.get("phone", "").strip()
        education = request.form.get("education", "").strip()
        experience = float(request.form.get("experience_years", 0))
        location = request.form.get("location", "").strip()
        resume_text = request.form.get("resume_text", "").strip()
        skill_names = [x.strip() for x in request.form.get("skills", "").split(",") if x.strip()]

        db = get_db()
        cur = db.cursor()
        try:
            cur.execute("""
                INSERT INTO candidates
                (name, email, phone, education, experience_years, location, resume_text)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (name, email, phone, education, experience, location, resume_text))
            candidate_id = cur.lastrowid

            candidate_skill_names = list(skill_names)
            if not candidate_skill_names and resume_text:
                cur.execute("SELECT skill_name FROM skills")
                all_skills = [row[0] for row in cur.fetchall()]
                candidate_skill_names = extract_skills(resume_text, all_skills)

            for skill_name in candidate_skill_names:
                cur.execute("INSERT IGNORE INTO skills(skill_name) VALUES (%s)", (skill_name,))
                cur.execute("SELECT skill_id FROM skills WHERE skill_name=%s", (skill_name,))
                skill_id = cur.fetchone()[0]
                cur.execute("""
                    INSERT IGNORE INTO candidate_skills(candidate_id, skill_id, proficiency, years_experience)
                    VALUES (%s,%s,'Intermediate',%s)
                """, (candidate_id, skill_id, experience))

            db.commit()
            flash("Candidate added successfully.", "success")
            return redirect(url_for("candidates"))
        except Exception as e:
            db.rollback()
            flash(f"Could not add candidate: {e}", "danger")
        finally:
            cur.close(); db.close()
    return render_template("add_candidate.html")

@app.route("/jobs")
def jobs():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM jobs ORDER BY job_id DESC")
    rows = cur.fetchall()
    cur.close(); db.close()
    return render_template("jobs.html", jobs=rows)

@app.route("/jobs/add", methods=["GET", "POST"])
def add_job():
    if request.method == "POST":
        title = request.form["job_title"].strip()
        company = request.form["company"].strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        min_exp = float(request.form.get("min_experience", 0))
        skill_names = [x.strip() for x in request.form.get("skills", "").split(",") if x.strip()]

        db = get_db()
        cur = db.cursor()
        try:
            cur.execute("""
                INSERT INTO jobs(job_title, company, location, description, min_experience, status)
                VALUES (%s,%s,%s,%s,%s,'Open')
            """, (title, company, location, description, min_exp))
            job_id = cur.lastrowid

            for name in skill_names:
                cur.execute("INSERT IGNORE INTO skills(skill_name) VALUES (%s)", (name,))
                cur.execute("SELECT skill_id FROM skills WHERE skill_name=%s", (name,))
                skill_id = cur.fetchone()[0]
                cur.execute("""
                    INSERT IGNORE INTO job_skills(job_id, skill_id, required_level, importance)
                    VALUES (%s,%s,'Intermediate',1)
                """, (job_id, skill_id))

            db.commit()
            flash("Job added successfully.", "success")
            return redirect(url_for("jobs"))
        except Exception as e:
            db.rollback()
            flash(f"Could not add job: {e}", "danger")
        finally:
            cur.close(); db.close()
    return render_template("add_job.html")

@app.route("/analyze/<int:candidate_id>/<int:job_id>")
def analyze(candidate_id, job_id):
    result = analyze_candidate_for_job(candidate_id, job_id)
    if result.get("error"):
        flash(result["error"], "danger")
        return redirect(url_for("dashboard"))
    return render_template("analysis.html", result=result)

@app.route("/rank/<int:job_id>")
def rank(job_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM jobs WHERE job_id=%s", (job_id,))
    job = cur.fetchone()
    cur.execute("""
        SELECT c.* FROM candidates c
        JOIN applications a ON a.candidate_id=c.candidate_id
        WHERE a.job_id=%s
    """, (job_id,))
    candidate_rows = cur.fetchall()
    cur.close(); db.close()

    results = []
    for c in candidate_rows:
        r = analyze_candidate_for_job(c["candidate_id"], job_id)
        if not r.get("error"):
            results.append(r)
    results.sort(key=lambda x: x["overall_score"], reverse=True)
    return render_template("ranking.html", job=job, results=results)

@app.route("/applications")
def applications():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT a.application_id, c.name AS candidate_name, j.job_title, a.status, a.application_date
        FROM applications a
        JOIN candidates c ON c.candidate_id = a.candidate_id
        JOIN jobs j ON j.job_id = a.job_id
        ORDER BY a.application_date DESC
    """)
    rows = cur.fetchall()
    cur.close(); db.close()
    return render_template("applications.html", applications=rows)

@app.route("/jobs/<int:job_id>/apply", methods=["GET", "POST"])
def apply_to_job(job_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM jobs WHERE job_id=%s", (job_id,))
    job = cur.fetchone()
    cur.execute("SELECT * FROM candidates ORDER BY candidate_id DESC")
    candidates = cur.fetchall()
    cur.close(); db.close()

    if not job:
        flash("Job not found.", "danger")
        return redirect(url_for("jobs"))

    if request.method == "POST":
        candidate_id = request.form.get("candidate_id")
        if not candidate_id:
            flash("Please select a candidate.", "warning")
            return redirect(url_for("apply_to_job", job_id=job_id))

        db = get_db()
        cur = db.cursor()
        try:
            cur.execute("""
                INSERT INTO applications(candidate_id, job_id, status)
                VALUES (%s, %s, 'Applied')
                ON DUPLICATE KEY UPDATE status='Applied'
            """, (candidate_id, job_id))
            db.commit()
            flash("Application submitted successfully.", "success")
        except Exception as e:
            db.rollback()
            flash(f"Application failed: {e}", "danger")
        finally:
            cur.close(); db.close()
        return redirect(url_for("jobs"))

    return render_template("apply_to_job.html", job=job, candidates=candidates)

@app.route("/apply/<int:candidate_id>/<int:job_id>", methods=["POST"])
def apply(candidate_id, job_id):
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("""
            INSERT INTO applications(candidate_id, job_id, status)
            VALUES (%s,%s,'Applied')
            ON DUPLICATE KEY UPDATE status='Applied'
        """, (candidate_id, job_id))
        db.commit()
        flash("Application created.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Application failed: {e}", "danger")
    finally:
        cur.close(); db.close()
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(debug=True)
