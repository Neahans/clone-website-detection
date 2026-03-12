import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Load datasets
fake_urls = pd.read_csv("fake.csv")
legit_urls = pd.read_csv("legitimate.csv")
url_mapping = pd.read_csv("url_mapping.csv")

# Standardize column names (assuming 'url' and 'type' exist in both datasets)
fake_urls.columns = ['url', 'type']
legit_urls.columns = ['url', 'type']
url_mapping.columns = ['fake_url', 'legit_url']  # Ensure correct column names

# Combine datasets
data = pd.concat([fake_urls, legit_urls], ignore_index=True)

# Convert labels to numeric (phishing/malicious = 1, legitimate = 0)
data['label'] = data['type'].apply(lambda x: 1 if x in ['phishing', 'malicious'] else 0)

# Use a random subset (reduce data size for faster training while maintaining accuracy)
data_sampled = data.sample(frac=0.5, random_state=42)  # Use 50% of the data

# Extract features (URL text)
vectorizer = CountVectorizer()
X_features = vectorizer.fit_transform(data_sampled['url'])
y_labels = data_sampled['label'].values

# Introduce slight label noise (randomly flip 3% of labels to avoid overfitting)
num_flip = int(0.03 * len(y_labels))  # 3% of total dataset
flip_indices = np.random.choice(len(y_labels), num_flip, replace=False)
for idx in flip_indices:
    y_labels[idx] = 1 - y_labels[idx]  # Flip 1 → 0, 0 → 1

# Split data into training and test sets
X_train, X_test, y_train, y_test = train_test_split(X_features, y_labels, test_size=0.2, random_state=42)

# Train the optimized XGBoost model
model = xgb.XGBClassifier(
    eval_metric='logloss',
    max_depth=3,            # Reduce depth further to prevent overfitting
    n_estimators=40,        # Reduce number of trees
    learning_rate=0.08,     # Slightly lower learning rate
    n_jobs=-1
)
model.fit(X_train, y_train)

# Evaluate model accuracy
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"Model Accuracy: {accuracy * 100:.2f}%")

# Save trained model and vectorizer
joblib.dump(model, "XGboost_model.pkl")
joblib.dump(vectorizer, "vectorizer.pkl")
print("Model training complete. Model saved as XGboost.pkl")

# Load model and vectorizer
def load_model():
    global model, vectorizer, url_mapping
    model = joblib.load("model.pkl")
    vectorizer = joblib.load("vectorizer.pkl")
    url_mapping = pd.read_csv("datasets/url_mapping.csv")

# Function to predict URL category and return correct URL if phishing
def predict_url(url):
    transformed_url = vectorizer.transform([url])
    prediction = model.predict(transformed_url)
    if prediction[0] == 1:
        # Check if phishing URL exists in mapping dataset
        correct_url = url_mapping[url_mapping['fake_url'] == url]['legit_url']
        if not correct_url.empty:
            return "Phishing", correct_url.values[0]
        return "Phishing", None
    return "Legitimate", None