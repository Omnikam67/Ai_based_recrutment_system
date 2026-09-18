USE talent_acquisition;

-- 1. DDL
ALTER TABLE candidates ADD COLUMN profile_status VARCHAR(20) DEFAULT 'Active';

-- 2. DML
INSERT INTO candidates(name,email) VALUES ('Demo User','demo@example.com');
UPDATE candidates SET location='Amravati' WHERE email='demo@example.com';
DELETE FROM candidates WHERE email='demo@example.com';
SELECT * FROM candidates;

-- 3. Constraints are defined in schema.sql.

-- 4. Aggregate functions
SELECT COUNT(*) AS total_candidates FROM candidates;
SELECT AVG(experience_years) AS average_experience FROM candidates;
SELECT MAX(experience_years) AS max_experience FROM candidates;
SELECT MIN(experience_years) AS min_experience FROM candidates;
SELECT SUM(experience_years) AS total_experience FROM candidates;

-- 5. Joins
SELECT c.name, s.skill_name, cs.proficiency
FROM candidates c
INNER JOIN candidate_skills cs ON c.candidate_id=cs.candidate_id
INNER JOIN skills s ON s.skill_id=cs.skill_id;

SELECT c.name, a.status
FROM candidates c
LEFT JOIN applications a ON c.candidate_id=a.candidate_id;

-- 6. TCL
START TRANSACTION;
UPDATE applications SET status='Shortlisted' WHERE application_id=1;
SAVEPOINT after_shortlist;
UPDATE applications SET status='Interview' WHERE application_id=1;
ROLLBACK TO after_shortlist;
COMMIT;

-- 7. Clauses
SELECT location, COUNT(*) AS total
FROM candidates
WHERE experience_years >= 1
GROUP BY location
HAVING COUNT(*) >= 1
ORDER BY total DESC;

SELECT DISTINCT education FROM candidates;

-- 8. Function and View
SELECT CalculateSkillMatch(1,1);
SELECT * FROM candidate_ranking ORDER BY overall_score DESC;

-- 9. Procedure
CALL GetTopCandidates(1);

-- Trigger demo:
-- UPDATE applications SET status='Selected' WHERE application_id=1;
-- Then check:
SELECT * FROM activity_log ORDER BY activity_date DESC;
