import joblib
import pandas as pd

model = joblib.load("candidate_model.pkl")


def predict_candidate(
    experience,
    skills_count,
    skill_match,
    education_score,
    interview_score
):
    candidate = pd.DataFrame([
        {
            "experience": experience,
            "skills_count": skills_count,
            "skill_match": skill_match,
            "education_score": education_score,
            "interview_score": interview_score
        }
    ])
    # it gives candidate selected or not
    prediction = model.predict(candidate)[0]
    #it gives probability score of that candidate matching to required job
    probability = model.predict_proba(candidate)[0][1]

    return {
        "prediction": int(prediction),
        "probability": round(probability * 100, 2)
    }