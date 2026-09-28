from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from db import get_db
from ai_engine import analyze_candidate_for_job, extract_skills
from ml_model import predict_candidate

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

HR_ROUTES = {"dashboard", "candidates", "add_candidate", "jobs", "add_job", "applications", "update_application_status", "apply_to_job", "analyze", "rank", "apply", "skills", "edit_skill", "delete_job", "interviews", "rankings", "hr_skill_gap"}
USER_ROUTES = {"user_dashboard", "my_applications", "user_apply", "candidate_jobs", "user_profile", "user_skills", "edit_user_skill", "user_skill_gap", "delete_user_profile"}


def is_candidate_role(role):
    return role in {"User", "Candidate"}


def get_current_candidate_id():
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT u.name, u.email, c.candidate_id
            FROM users u
            LEFT JOIN candidates c ON LOWER(c.email)=LOWER(u.email)
            WHERE u.user_id=%s
        """, (session["user_id"],))
        account = cur.fetchone()
        if account["candidate_id"] is None:
            cur.execute("INSERT INTO candidates(name, email) VALUES (%s, %s)",
                        (account["name"], account["email"]))
            db.commit()
            return cur.lastrowid
        return account["candidate_id"]
    finally:
        cur.close()
        db.close()


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
    user_id = session["user_id"]
    candidate_id = get_current_candidate_id()
    cur.execute("SELECT name, email FROM users WHERE user_id=%s", (user_id,))
    user = cur.fetchone()
    cur.execute("SELECT * FROM candidates WHERE candidate_id=%s", (candidate_id,))
    candidate = cur.fetchone()
    cur.execute("SELECT COUNT(*) AS total FROM candidate_skills WHERE candidate_id=%s", (candidate_id,))
    skills = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM applications WHERE candidate_id=%s", (candidate_id,))
    applications_count = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM applications WHERE candidate_id=%s AND status='Shortlisted'", (candidate_id,))
    shortlisted = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM applications WHERE candidate_id=%s AND status='Selected'", (candidate_id,))
    selected = cur.fetchone()["total"]
    cur.execute("""
        SELECT a.status, a.application_date, j.job_title, j.company
        FROM applications a JOIN jobs j ON j.job_id = a.job_id
        WHERE a.candidate_id=%s ORDER BY a.application_date DESC LIMIT 5
    """, (candidate_id,))
    recent_applications = cur.fetchall()
    cur.close(); db.close()
    return render_template("user_dashboard.html", user=user, candidate=candidate, skills=skills,
                           applications_count=applications_count, shortlisted=shortlisted,
                           selected=selected, recent_applications=recent_applications)


@app.route("/user/jobs")
def candidate_jobs():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT j.*, GROUP_CONCAT(s.skill_name ORDER BY s.skill_name SEPARATOR ', ') AS required_skills
        FROM jobs j
        LEFT JOIN job_skills js ON js.job_id=j.job_id
        LEFT JOIN skills s ON s.skill_id=js.skill_id
        WHERE j.status='Open'
        GROUP BY j.job_id ORDER BY j.job_id DESC
    """)
    jobs = cur.fetchall()
    cur.close(); db.close()
    return render_template("user_jobs.html", jobs=jobs)


@app.route("/user/profile")
def user_profile():
    candidate_id = get_current_candidate_id()
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT u.name, u.email, c.phone, c.education, c.experience_years, c.location
        FROM users u LEFT JOIN candidates c ON c.candidate_id=%s
        WHERE u.user_id=%s
    """, (candidate_id, session["user_id"]))
    profile = cur.fetchone()
    cur.execute("""
        SELECT s.skill_id, s.skill_name, cs.proficiency, cs.years_experience
        FROM candidate_skills cs JOIN skills s ON s.skill_id=cs.skill_id
        WHERE cs.candidate_id=%s ORDER BY s.skill_name
    """, (candidate_id,))
    skills = cur.fetchall()
    cur.execute("""
        SELECT s.skill_id, s.skill_name, s.category
        FROM skills s
        WHERE NOT EXISTS (
            SELECT 1 FROM candidate_skills cs
            WHERE cs.candidate_id=%s AND cs.skill_id=s.skill_id
        )
        ORDER BY s.skill_name
    """, (candidate_id,))
    available_skills = cur.fetchall()
    cur.close(); db.close()
    return render_template("user_profile.html", profile=profile, skills=skills,
                           available_skills=available_skills)


@app.route("/user/profile/delete", methods=["POST"])
def delete_user_profile():
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT c.candidate_id
            FROM users u JOIN candidates c ON LOWER(c.email)=LOWER(u.email)
            WHERE u.user_id=%s
        """, (session["user_id"],))
        candidate = cur.fetchone()
        if not candidate:
            flash("No candidate profile was found to delete.", "warning")
            return redirect(url_for("user_profile"))

        candidate_id = candidate["candidate_id"]
        cur.execute("DELETE FROM candidate_skills WHERE candidate_id=%s", (candidate_id,))
        cur.execute("DELETE FROM skill_gaps WHERE candidate_id=%s", (candidate_id,))
        cur.execute("DELETE FROM recommendations WHERE candidate_id=%s", (candidate_id,))
        cur.execute("DELETE FROM activity_log WHERE candidate_id=%s", (candidate_id,))
        cur.execute("""
            UPDATE candidates
            SET phone=NULL, education=NULL, experience_years=0, location=NULL, resume_text=NULL
            WHERE candidate_id=%s
        """, (candidate_id,))
        db.commit()
        flash("Your candidate profile details and skills were deleted. Your account and applications remain.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Could not delete your profile: {e}", "danger")
    finally:
        cur.close(); db.close()
    return redirect(url_for("user_profile"))


@app.route("/user/skills", methods=["GET", "POST"])
def user_skills():
    candidate_id = get_current_candidate_id()
    if request.method == "POST":
        redirect_endpoint = "user_profile" if request.form.get("return_to") == "profile" else "user_skills"
        skill_id = request.form.get("skill_id", type=int)
        proficiency = request.form.get("proficiency", "").strip()
        experience = request.form.get("years_experience", "").strip()
        if not skill_id or proficiency not in {"Beginner", "Intermediate", "Advanced", "Expert"}:
            flash("Select a skill and valid proficiency level.", "warning")
            return redirect(url_for(redirect_endpoint))

        try:
            years_experience = float(experience)
            if years_experience < 0:
                raise ValueError
        except ValueError:
            flash("Enter a valid non-negative number of years.", "warning")
            return redirect(url_for(redirect_endpoint))

        db = get_db()
        cur = db.cursor(dictionary=True)
        try:
            cur.execute("SELECT skill_name FROM skills WHERE skill_id=%s", (skill_id,))
            skill = cur.fetchone()
            if not skill:
                flash("Select a skill from the available list.", "warning")
                return redirect(url_for(redirect_endpoint))
            cur.execute("""
                SELECT skill_id FROM candidate_skills
                WHERE candidate_id=%s AND skill_id=%s
            """, (candidate_id, skill_id))
            if cur.fetchone():
                flash("That skill is already in your profile. Use Edit to update it.", "warning")
                return redirect(url_for(redirect_endpoint))
            cur.execute("""
                INSERT INTO candidate_skills(candidate_id, skill_id, proficiency, years_experience)
                VALUES (%s, %s, %s, %s)
            """, (candidate_id, skill_id, proficiency, years_experience))
            cur.execute("""
                INSERT INTO activity_log(candidate_id, activity)
                VALUES (%s, %s)
            """, (candidate_id, f"Added skill: {skill['skill_name']}"))
            db.commit()
            flash("Skill added to your profile.", "success")
        except Exception as e:
            db.rollback()
            flash(f"Could not add skill: {e}", "danger")
        finally:
            cur.close(); db.close()
        return redirect(url_for(redirect_endpoint))

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT s.skill_id, s.skill_name, cs.proficiency, cs.years_experience
        FROM candidate_skills cs JOIN skills s ON s.skill_id=cs.skill_id
        WHERE cs.candidate_id=%s ORDER BY s.skill_name
    """, (candidate_id,))
    skills = cur.fetchall()
    cur.execute("""
        SELECT s.skill_id, s.skill_name, s.category
        FROM skills s
        WHERE NOT EXISTS (
            SELECT 1 FROM candidate_skills cs
            WHERE cs.candidate_id=%s AND cs.skill_id=s.skill_id
        )
        ORDER BY s.skill_name
    """, (candidate_id,))
    available_skills = cur.fetchall()
    cur.close(); db.close()
    return render_template("user_skills.html", skills=skills, available_skills=available_skills)


@app.route("/user/skills/<int:skill_id>/edit", methods=["GET", "POST"])
def edit_user_skill(skill_id):
    candidate_id = get_current_candidate_id()
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT s.skill_id, s.skill_name, cs.proficiency, cs.years_experience
        FROM candidate_skills cs JOIN skills s ON s.skill_id=cs.skill_id
        WHERE cs.candidate_id=%s AND cs.skill_id=%s
    """, (candidate_id, skill_id))
    skill = cur.fetchone()
    if not skill:
        cur.close(); db.close()
        flash("That skill is not part of your profile.", "warning")
        return redirect(url_for("user_skills"))

    if request.method == "POST":
        proficiency = request.form.get("proficiency", "").strip()
        experience = request.form.get("years_experience", "").strip()
        if proficiency not in {"Beginner", "Intermediate", "Advanced", "Expert"}:
            flash("Select a valid proficiency level.", "warning")
        else:
            try:
                years_experience = float(experience)
                if years_experience < 0:
                    raise ValueError
                cur.execute("""
                    UPDATE candidate_skills SET proficiency=%s, years_experience=%s
                    WHERE candidate_id=%s AND skill_id=%s
                """, (proficiency, years_experience, candidate_id, skill_id))
                cur.execute("""
                    INSERT INTO activity_log(candidate_id, activity)
                    VALUES (%s, %s)
                """, (candidate_id, f"Updated skill: {skill['skill_name']}"))
                db.commit()
                cur.close(); db.close()
                flash("Skill details updated.", "success")
                return redirect(url_for("user_skills"))
            except ValueError:
                flash("Enter a valid non-negative number of years.", "warning")

    cur.close(); db.close()
    return render_template("edit_user_skill.html", skill=skill)


@app.route("/user/skill-gap")
def user_skill_gap():
    candidate_id = get_current_candidate_id()
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT job_id, job_title, company FROM jobs WHERE status='Open' ORDER BY job_title")
    jobs = cur.fetchall()
    cur.close(); db.close()

    result = None
    job_id = request.args.get("job_id", type=int)
    if job_id:
        result = analyze_candidate_for_job(candidate_id, job_id)
    return render_template("user_skill_gap.html", jobs=jobs, result=result, selected_job_id=job_id)

@app.route("/my-applications")
def my_applications():
    if not (session.get("user_role") in {"User", "Candidate"}):
        return redirect(url_for("dashboard"))

    db = get_db()
    cur = db.cursor(dictionary=True)
    candidate_id = get_current_candidate_id()
    cur.execute("""
        SELECT a.application_id, a.status, a.application_date, j.job_title, j.company, j.location
        FROM applications a
        JOIN jobs j ON j.job_id = a.job_id
        WHERE a.candidate_id = %s
        ORDER BY a.application_date DESC
    """, (candidate_id,))
    rows = cur.fetchall()
    cur.close(); db.close()
    return render_template("my_applications.html", applications=rows)

@app.route("/user/apply/<int:job_id>", methods=["POST"])
def user_apply(job_id):
    if not (session.get("user_role") in {"User", "Candidate"}):
        return redirect(url_for("dashboard"))

    db = get_db()
    cur = db.cursor()
    candidate_id = get_current_candidate_id()
    try:
        cur.execute("""
            INSERT INTO applications(candidate_id, job_id, status)
            VALUES (%s, %s, 'Applied')
            ON DUPLICATE KEY UPDATE status='Applied'
        """, (candidate_id, job_id))
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
    cur.execute("SELECT COUNT(*) AS total FROM applications WHERE status='Selected'")
    selected = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM skills")
    skills = cur.fetchone()["total"]
    cur.execute("""
        SELECT a.application_id, c.name AS candidate_name, j.job_title, a.status, a.application_date
        FROM applications a JOIN candidates c ON c.candidate_id=a.candidate_id
        JOIN jobs j ON j.job_id=a.job_id
        ORDER BY a.application_date DESC LIMIT 5
    """)
    recent_applications = cur.fetchall()
    cur.execute("""
        SELECT name, email, education, experience_years, created_at
        FROM candidates ORDER BY created_at DESC LIMIT 5
    """)
    recent_candidates = cur.fetchall()
    cur.execute("SELECT status, COUNT(*) AS total FROM jobs GROUP BY status ORDER BY status")
    job_statistics = cur.fetchall()
    cur.execute("SELECT status, COUNT(*) AS total FROM applications GROUP BY status ORDER BY status")
    application_status = cur.fetchall()
    cur.execute("""
        SELECT c.name AS candidate_name, al.activity, al.activity_date
        FROM activity_log al
        JOIN candidates c ON c.candidate_id=al.candidate_id
        ORDER BY al.activity_date DESC LIMIT 8
    """)
    recent_activity = cur.fetchall()
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
                           applications=applications, shortlisted=shortlisted, selected=selected,
                           skills=skills, recent_applications=recent_applications,
                           recent_candidates=recent_candidates, job_statistics=job_statistics,
                           application_status=application_status, recent_activity=recent_activity,
                           top=top)

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
    cur.execute("""
        SELECT j.*, GROUP_CONCAT(s.skill_name ORDER BY s.skill_name SEPARATOR ', ') AS required_skills
        FROM jobs j
        LEFT JOIN job_skills js ON js.job_id=j.job_id
        LEFT JOIN skills s ON s.skill_id=js.skill_id
        GROUP BY j.job_id ORDER BY j.job_id DESC
    """)
    rows = cur.fetchall()
    cur.close(); db.close()
    return render_template("jobs.html", jobs=rows)


@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
def delete_job(job_id):
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("DELETE FROM jobs WHERE job_id=%s", (job_id,))
        if cur.rowcount:
            db.commit()
            flash("Job and its linked applications, interviews, and analysis records were deleted.", "success")
        else:
            db.rollback()
            flash("Job not found.", "warning")
    except Exception as e:
        db.rollback()
        flash(f"Could not delete job: {e}", "danger")
    finally:
        cur.close(); db.close()
    return redirect(url_for("jobs"))

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
    results.sort(key=lambda x: (x["skill_score"], x["overall_score"]), reverse=True)
    return render_template("ranking.html", job=job, results=results)

@app.route("/applications")
def applications():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT a.application_id, a.candidate_id, a.job_id, c.name AS candidate_name,
               j.job_title, a.status, a.application_date
        FROM applications a
        JOIN candidates c ON c.candidate_id = a.candidate_id
        JOIN jobs j ON j.job_id = a.job_id
        ORDER BY a.application_date DESC
    """)
    rows = cur.fetchall()
    cur.close(); db.close()
    for application in rows:
        result = analyze_candidate_for_job(application["candidate_id"], application["job_id"])
        application["skill_score"] = result.get("skill_score")
        application["overall_score"] = result.get("overall_score")
    rows.sort(key=lambda application: (
        application["skill_score"] or 0,
        application["overall_score"] or 0
    ), reverse=True)
    return render_template("applications.html", applications=rows)


@app.route("/applications/<int:application_id>/status", methods=["POST"])
def update_application_status(application_id):
    status = request.form.get("status", "").strip()
    if status not in {"Applied", "Shortlisted", "Interview", "Selected", "Rejected"}:
        flash("Select a valid application status.", "warning")
        return redirect(url_for("applications"))

    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("UPDATE applications SET status=%s WHERE application_id=%s",
                    (status, application_id))
        if cur.rowcount:
            db.commit()
            flash("Application status updated.", "success")
        else:
            db.rollback()
            flash("Application not found or status unchanged.", "warning")
    except Exception as e:
        db.rollback()
        flash(f"Could not update application status: {e}", "danger")
    finally:
        cur.close(); db.close()
    return redirect(url_for("applications"))


@app.route("/skills", methods=["GET", "POST"])
def skills():
    if request.method == "POST":
        skill_name = request.form.get("skill_name", "").strip()
        category = request.form.get("category", "").strip() or "Technical"
        if not skill_name:
            flash("Skill name is required.", "warning")
            return redirect(url_for("skills"))

        db = get_db()
        cur = db.cursor()
        try:
            cur.execute(
                "INSERT IGNORE INTO skills(skill_name, category) VALUES (%s, %s)",
                (skill_name, category)
            )
            if cur.rowcount:
                db.commit()
                flash("Skill added.", "success")
            else:
                db.rollback()
                flash("That skill already exists.", "warning")
        except Exception as e:
            db.rollback()
            flash(f"Could not add skill: {e}", "danger")
        finally:
            cur.close(); db.close()
        return redirect(url_for("skills"))

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT s.skill_id, s.skill_name, s.category,
               COUNT(DISTINCT cs.candidate_id) AS candidate_count,
               COUNT(DISTINCT js.job_id) AS job_count
        FROM skills s
        LEFT JOIN candidate_skills cs ON cs.skill_id=s.skill_id
        LEFT JOIN job_skills js ON js.skill_id=s.skill_id
        GROUP BY s.skill_id, s.skill_name, s.category
        ORDER BY s.skill_name
    """)
    rows = cur.fetchall()
    cur.close(); db.close()
    return render_template("skills.html", skills=rows)


@app.route("/skills/<int:skill_id>/edit", methods=["GET", "POST"])
def edit_skill(skill_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT skill_id, skill_name, category FROM skills WHERE skill_id=%s", (skill_id,))
    skill = cur.fetchone()
    if not skill:
        cur.close(); db.close()
        flash("Skill not found.", "warning")
        return redirect(url_for("skills"))

    if request.method == "POST":
        skill_name = request.form.get("skill_name", "").strip()
        category = request.form.get("category", "").strip()
        if not skill_name:
            flash("Skill name is required.", "warning")
        else:
            try:
                cur.execute("UPDATE skills SET skill_name=%s, category=%s WHERE skill_id=%s",
                            (skill_name, category or "Technical", skill_id))
                db.commit()
                cur.close(); db.close()
                flash("Skill updated.", "success")
                return redirect(url_for("skills"))
            except Exception as e:
                db.rollback()
                flash(f"Could not update skill: {e}", "danger")

    cur.close(); db.close()
    return render_template("edit_skill.html", skill=skill)


@app.route("/interviews", methods=["GET", "POST"])
def interviews():
    if request.method == "POST":
        application_id = request.form.get("application_id", type=int)
        interview_date_value = request.form.get("interview_date", "").strip()
        interviewer = request.form.get("interviewer", "").strip()
        if not application_id or not interview_date_value or not interviewer:
            flash("Choose an application, date, and interviewer.", "warning")
            return redirect(url_for("interviews"))

        try:
            interview_date = datetime.fromisoformat(interview_date_value)
        except ValueError:
            flash("Enter a valid interview date and time.", "warning")
            return redirect(url_for("interviews"))

        db = get_db()
        cur = db.cursor()
        try:
            cur.execute("""
                INSERT INTO interviews(application_id, interview_date, interviewer, status)
                SELECT application_id, %s, %s, 'Scheduled'
                FROM applications
                WHERE application_id=%s AND status != 'Rejected' AND status != 'Selected'
            """, (interview_date, interviewer, application_id))
            if cur.rowcount:
                cur.execute("UPDATE applications SET status='Interview' WHERE application_id=%s",
                            (application_id,))
                db.commit()
                flash("Interview scheduled.", "success")
            else:
                db.rollback()
                flash("Choose an active application to schedule an interview.", "warning")
        except Exception as e:
            db.rollback()
            flash(f"Could not schedule interview: {e}", "danger")
        finally:
            cur.close(); db.close()
        return redirect(url_for("interviews"))

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT i.interview_id, i.application_id, i.interview_date, i.interviewer, i.status, i.feedback,
               c.name AS candidate_name, j.job_title
        FROM interviews i
        JOIN applications a ON a.application_id=i.application_id
        JOIN candidates c ON c.candidate_id=a.candidate_id
        JOIN jobs j ON j.job_id=a.job_id
        ORDER BY i.interview_date DESC
    """)
    rows = cur.fetchall()
    cur.execute("""
        SELECT a.application_id, a.status, c.name AS candidate_name, j.job_title
        FROM applications a
        JOIN candidates c ON c.candidate_id=a.candidate_id
        JOIN jobs j ON j.job_id=a.job_id
        WHERE a.status NOT IN ('Rejected', 'Selected')
        ORDER BY a.application_date DESC
    """)
    applications_for_interview = cur.fetchall()
    cur.close(); db.close()
    return render_template("interviews.html", interviews=rows,
                           applications=applications_for_interview)


@app.route("/interviews/<int:interview_id>/update", methods=["POST"])
def update_interview(interview_id):
    status = request.form.get("status", "").strip()
    feedback = request.form.get("feedback", "").strip()
    allowed_statuses = {"Scheduled", "Completed", "Passed", "Rejected", "Next Round", "Cancelled"}
    if status not in allowed_statuses:
        flash("Select a valid interview status.", "warning")
        return redirect(url_for("interviews"))

    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("UPDATE interviews SET status=%s, feedback=%s WHERE interview_id=%s",
                    (status, feedback, interview_id))
        if cur.rowcount:
            if status == "Rejected":
                cur.execute("""
                    UPDATE applications a
                    JOIN interviews i ON i.application_id=a.application_id
                    SET a.status='Rejected'
                    WHERE i.interview_id=%s
                """, (interview_id,))
            db.commit()
            flash("Interview details updated.", "success")
        else:
            db.rollback()
            flash("Interview not found or no changes were made.", "warning")
    except Exception as e:
        db.rollback()
        flash(f"Could not update interview: {e}", "danger")
    finally:
        cur.close(); db.close()
    return redirect(url_for("interviews"))


@app.route("/rankings")
def rankings():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT job_id, job_title, company, location, status FROM jobs ORDER BY job_id DESC")
    rows = cur.fetchall()
    cur.close(); db.close()
    return render_template("rankings.html", jobs=rows)


@app.route("/skill-gap")
def hr_skill_gap():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT candidate_id, name, email FROM candidates ORDER BY name")
    candidates = cur.fetchall()
    cur.execute("SELECT job_id, job_title, company FROM jobs ORDER BY job_title")
    jobs = cur.fetchall()
    cur.close(); db.close()

    result = None
    candidate_id = request.args.get("candidate_id", type=int)
    job_id = request.args.get("job_id", type=int)
    if candidate_id and job_id:
        result = analyze_candidate_for_job(candidate_id, job_id)
    return render_template("skill_gap.html", candidates=candidates, jobs=jobs,
                           result=result, selected_candidate_id=candidate_id,
                           selected_job_id=job_id)

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
