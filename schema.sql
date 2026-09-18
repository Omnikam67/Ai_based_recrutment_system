CREATE DATABASE IF NOT EXISTS talent_acquisition;
USE talent_acquisition;

DROP VIEW IF EXISTS candidate_ranking;
DROP TRIGGER IF EXISTS trg_application_selection;
DROP PROCEDURE IF EXISTS GetTopCandidates;
DROP FUNCTION IF EXISTS CalculateSkillMatch;

DROP TABLE IF EXISTS activity_log;
DROP TABLE IF EXISTS recommendations;
DROP TABLE IF EXISTS interviews;
DROP TABLE IF EXISTS skill_gaps;
DROP TABLE IF EXISTS candidate_scores;
DROP TABLE IF EXISTS applications;
DROP TABLE IF EXISTS job_skills;
DROP TABLE IF EXISTS candidate_skills;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS skills;
DROP TABLE IF EXISTS candidates;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(30) DEFAULT 'HR'
);

CREATE TABLE candidates (
    candidate_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(20),
    education VARCHAR(150),
    experience_years DECIMAL(4,1) DEFAULT 0 CHECK (experience_years >= 0),
    location VARCHAR(100),
    resume_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE skills (
    skill_id INT PRIMARY KEY AUTO_INCREMENT,
    skill_name VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(80) DEFAULT 'Technical'
);

CREATE TABLE jobs (
    job_id INT PRIMARY KEY AUTO_INCREMENT,
    job_title VARCHAR(150) NOT NULL,
    company VARCHAR(150) NOT NULL,
    location VARCHAR(100),
    description TEXT,
    min_experience DECIMAL(4,1) DEFAULT 0 CHECK (min_experience >= 0),
    status VARCHAR(30) DEFAULT 'Open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE candidate_skills (
    candidate_id INT NOT NULL,
    skill_id INT NOT NULL,
    proficiency ENUM('Beginner','Intermediate','Advanced','Expert') DEFAULT 'Beginner',
    years_experience DECIMAL(4,1) DEFAULT 0,
    PRIMARY KEY(candidate_id, skill_id),
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY(skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE
);

CREATE TABLE job_skills (
    job_id INT NOT NULL,
    skill_id INT NOT NULL,
    required_level ENUM('Beginner','Intermediate','Advanced','Expert') DEFAULT 'Intermediate',
    importance INT DEFAULT 1 CHECK (importance BETWEEN 1 AND 5),
    PRIMARY KEY(job_id, skill_id),
    FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY(skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE
);

CREATE TABLE applications (
    application_id INT PRIMARY KEY AUTO_INCREMENT,
    candidate_id INT NOT NULL,
    job_id INT NOT NULL,
    application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('Applied','Shortlisted','Interview','Selected','Rejected') DEFAULT 'Applied',
    UNIQUE(candidate_id, job_id),
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE TABLE candidate_scores (
    score_id INT PRIMARY KEY AUTO_INCREMENT,
    candidate_id INT NOT NULL,
    job_id INT NOT NULL,
    skill_score DECIMAL(6,2) DEFAULT 0,
    experience_score DECIMAL(6,2) DEFAULT 0,
    education_score DECIMAL(6,2) DEFAULT 0,
    nlp_similarity DECIMAL(6,2) DEFAULT 0,
    overall_score DECIMAL(6,2) DEFAULT 0,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE(candidate_id, job_id),
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE TABLE skill_gaps (
    gap_id INT PRIMARY KEY AUTO_INCREMENT,
    candidate_id INT NOT NULL,
    job_id INT NOT NULL,
    skill_id INT NOT NULL,
    required_level VARCHAR(30),
    candidate_level VARCHAR(30),
    gap_level VARCHAR(30),
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY(skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE
);

CREATE TABLE recommendations (
    recommendation_id INT PRIMARY KEY AUTO_INCREMENT,
    candidate_id INT NOT NULL,
    skill_id INT NOT NULL,
    recommendation VARCHAR(255),
    priority VARCHAR(20),
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY(skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE
);

CREATE TABLE interviews (
    interview_id INT PRIMARY KEY AUTO_INCREMENT,
    application_id INT NOT NULL,
    interview_date DATETIME,
    interviewer VARCHAR(100),
    status VARCHAR(30) DEFAULT 'Scheduled',
    feedback TEXT,
    FOREIGN KEY(application_id) REFERENCES applications(application_id) ON DELETE CASCADE
);

CREATE TABLE activity_log (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    candidate_id INT NOT NULL,
    activity VARCHAR(255) NOT NULL,
    activity_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
);

-- VIEW: objective 8
CREATE VIEW candidate_ranking AS
SELECT
    cs.score_id, c.candidate_id, c.name, j.job_id, j.job_title,
    cs.skill_score, cs.experience_score, cs.education_score,
    cs.nlp_similarity, cs.overall_score,
    RANK() OVER (PARTITION BY cs.job_id ORDER BY cs.overall_score DESC) AS candidate_rank
FROM candidate_scores cs
JOIN candidates c ON c.candidate_id=cs.candidate_id
JOIN jobs j ON j.job_id=cs.job_id;

DELIMITER $$

-- FUNCTION: objective 8
CREATE FUNCTION CalculateSkillMatch(p_candidate_id INT, p_job_id INT)
RETURNS DECIMAL(6,2)
DETERMINISTIC
BEGIN
    DECLARE required_count INT DEFAULT 0;
    DECLARE matched_count INT DEFAULT 0;

    SELECT COUNT(*) INTO required_count
    FROM job_skills WHERE job_id=p_job_id;

    SELECT COUNT(*) INTO matched_count
    FROM job_skills js
    JOIN candidate_skills cs
      ON cs.skill_id=js.skill_id AND cs.candidate_id=p_candidate_id
    WHERE js.job_id=p_job_id;

    IF required_count=0 THEN RETURN 0;
    END IF;

    RETURN (matched_count / required_count) * 100;
END$$

-- STORED PROCEDURE: objective 9
CREATE PROCEDURE GetTopCandidates(IN p_job_id INT)
BEGIN
    SELECT candidate_id, name, job_title, overall_score, candidate_rank
    FROM candidate_ranking
    WHERE job_id=p_job_id
    ORDER BY overall_score DESC;
END$$

-- TRIGGER: objective 9
CREATE TRIGGER trg_application_selection
AFTER UPDATE ON applications
FOR EACH ROW
BEGIN
    IF NEW.status='Selected' AND OLD.status<>'Selected' THEN
        INSERT INTO activity_log(candidate_id, activity)
        VALUES (NEW.candidate_id, 'Candidate selected for job');
    END IF;
END$$

DELIMITER ;
