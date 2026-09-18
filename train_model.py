import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

# Load dataset
data = pd.read_csv("ml_dataset.csv")

# Features
X = data[
    [
        "experience",
        "skills_count",
        "skill_match",
        "education_score",
        "interview_score"
    ]
]

# Target
y = data["selected"]

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)

# Create model
model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)

# Train
model.fit(X_train, y_train)

# Prediction
y_pred = model.predict(X_test)

# Evaluation
accuracy = accuracy_score(y_test, y_pred)

print("Accuracy:", accuracy)
print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# Save model
joblib.dump(model, "candidate_model.pkl")

print("\nModel saved as candidate_model.pkl")

# Feature importance
print("\nFeature Importance:")

for feature, importance in zip(X.columns, model.feature_importances_):
    print(feature, ":", importance)