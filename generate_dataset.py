import pandas as pd
import random

random.seed(42)

data = []

for i in range(500):

    # Candidate features
    experience = random.randint(0, 8)
    skills_count = random.randint(2, 12)
    skill_match = random.randint(30, 100)
    education_score = random.randint(50, 95)
    interview_score = random.randint(40, 100)

    # Calculate a realistic academic/demo hiring score
    score = (
        experience * 3
        + skills_count * 2
        + skill_match * 0.35
        + education_score * 0.10
        + interview_score * 0.20
    )

    # Add a small amount of randomness
    score += random.uniform(-10, 10)

    # Target
    if score >= 65:
        selected = 1
    else:
        selected = 0

    data.append([
        experience,
        skills_count,
        skill_match,
        education_score,
        interview_score,
        selected
    ])


df = pd.DataFrame(
    data,
    columns=[
        "experience",
        "skills_count",
        "skill_match",
        "education_score",
        "interview_score",
        "selected"
    ]
)

df.to_csv("ml_dataset.csv", index=False)

print("Dataset created successfully!")
print("Total records:", len(df))
print("\nClass distribution:")
print(df["selected"].value_counts())

print("\nFirst 10 records:")
print(df.head(10))