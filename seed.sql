USE talent_acquisition;

INSERT IGNORE INTO users(name,email,password,role) VALUES
('HR Admin','hr@example.com','admin123','HR');

INSERT IGNORE INTO skills(skill_name,category) VALUES
('Python','Programming'),('SQL','Database'),('MySQL','Database'),
('Flask','Backend'),('Machine Learning','AI'),
('Pandas','Data Science'),('NumPy','Data Science'),
('Scikit-learn','AI'),('Git','Tools'),('Docker','DevOps'),
('JavaScript','Frontend'),('HTML','Frontend'),('CSS','Frontend');

INSERT INTO candidates
(name,email,phone,education,experience_years,location,resume_text)
VALUES
('Rahul Sharma','rahul@example.com','9876543210','B.Tech Computer Science',2,'Pune',
 'Python SQL Flask MySQL Git Pandas NumPy developed machine learning applications and REST APIs'),
('Priya Patil','priya@example.com','9876543211','B.Tech AI Data Science',3,'Mumbai',
 'Python SQL Machine Learning Pandas NumPy Scikit-learn Git Flask data science and NLP projects'),
('Amit Verma','amit@example.com','9876543212','B.E. Computer Engineering',1,'Nagpur',
 'JavaScript HTML CSS SQL Git Python basic web development');

INSERT INTO candidate_skills(candidate_id,skill_id,proficiency,years_experience)
SELECT c.candidate_id,s.skill_id,'Advanced',2
FROM candidates c JOIN skills s ON s.skill_name IN ('Python','SQL','Flask')
WHERE c.email='rahul@example.com';

INSERT INTO candidate_skills(candidate_id,skill_id,proficiency,years_experience)
SELECT c.candidate_id,s.skill_id,'Advanced',3
FROM candidates c JOIN skills s ON s.skill_name IN ('Python','SQL','Machine Learning','Pandas','NumPy','Scikit-learn','Flask')
WHERE c.email='priya@example.com';

INSERT INTO candidate_skills(candidate_id,skill_id,proficiency,years_experience)
SELECT c.candidate_id,s.skill_id,'Intermediate',1
FROM candidates c JOIN skills s ON s.skill_name IN ('JavaScript','HTML','CSS','SQL','Python','Git')
WHERE c.email='amit@example.com';

INSERT INTO jobs(job_title,company,location,description,min_experience,status)
VALUES
('AI/ML Engineer','TechNova','Bengaluru',
 'We need a Python and SQL developer with Machine Learning, Pandas, NumPy, Scikit-learn, Flask, Git and Docker experience.',
 2,'Open');

SET @job_id = LAST_INSERT_ID();

INSERT INTO job_skills(job_id,skill_id,required_level,importance)
SELECT @job_id, skill_id,
       CASE WHEN skill_name IN ('Python','Machine Learning','SQL') THEN 'Advanced' ELSE 'Intermediate' END,
       CASE WHEN skill_name IN ('Python','Machine Learning') THEN 5 ELSE 3 END
FROM skills
WHERE skill_name IN ('Python','SQL','Machine Learning','Pandas','NumPy','Scikit-learn','Flask','Git','Docker');

INSERT IGNORE INTO applications(candidate_id,job_id,status)
SELECT candidate_id,@job_id,'Applied' FROM candidates;
