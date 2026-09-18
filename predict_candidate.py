import joblib
import pandas as pd

# Load trained model
model = joblib.load("candidate_model.pkl")

# Candidate data
candidate = pd.DataFrame([
    {
        "experience": 3,
        "skills_count": 8,
        "skill_match": 82,
        "education_score": 80,
        "interview_score": 85
    }
])

# Prediction
prediction = model.predict(candidate)[0]

# Probability
probability = model.predict_proba(candidate)[0][1]

if prediction == 1:
    result = "Selected"
else:
    result = "Not Selected"

print("Prediction:", result)
print("Selection Probability:", round(probability * 100, 2), "%")