# AI-Based Talent Acquisition & Skill Gap Analytics Platform

## Project
HR Tech platform for candidate ranking and skill-gap analysis.

## Technology
- Frontend: HTML, CSS, JavaScript
- Backend: Python Flask
- Database: MySQL
- AI: NLP TF-IDF/cosine similarity + skill extraction + explainable scoring
- ML library: scikit-learn

## AI score
Overall Score =
60% Skill Match +
20% Experience +
10% Education +
10% NLP Similarity

## DBMS syllabus coverage
1. DDL: CREATE, ALTER/DROP examples and schema creation
2. DML: INSERT, UPDATE, DELETE, SELECT
3. Constraints: PK, FK, UNIQUE, NOT NULL, CHECK, DEFAULT
4. Aggregate functions: COUNT, AVG, MIN, MAX, SUM
5. Joins: INNER/LEFT joins across candidate/job/skill tables
6. TCL: COMMIT, ROLLBACK, SAVEPOINT
7. SQL clauses: WHERE, GROUP BY, HAVING, ORDER BY, DISTINCT
8. Functions and Views: CalculateSkillMatch and candidate_ranking
9. Stored Procedure and Trigger: GetTopCandidates and selection log trigger
10. Integrated mini-project: complete recruitment analytics system

## Setup
1. Install MySQL 8+ and Python 3.11+.
2. Create database:
   mysql -u root -p < schema.sql
3. Insert sample data:
   mysql -u root -p talent_acquisition < seed.sql
4. Create virtual environment:
   python -m venv venv
5. Activate it:
   Windows: venv\Scripts\activate
6. Install:
   pip install -r requirements.txt
7. Set DB_PASSWORD in your environment, or edit db.py.
8. Run:
   python app.py
9. Open http://127.0.0.1:5000

## Demo
- Dashboard shows HR KPIs.
- Candidates page shows candidates.
- Jobs page shows jobs.
- Add a candidate/job.
- Apply a candidate to a job.
- Open ranking for a job.
- Analyze a candidate to see matched skills, missing skills, AI score and NLP similarity.

## Important
This is an academic prototype. Do not use it as an automated real-world hiring decision system without human review, fairness testing, privacy controls and legal compliance.
