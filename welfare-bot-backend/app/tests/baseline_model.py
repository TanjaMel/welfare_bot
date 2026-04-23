from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

texts = [
    "I feel fine",
    "I am very tired and dizzy",
    "I fell and have chest pain",
    "I feel lonely and sad",
]

labels = ["low", "medium", "critical", "medium"]

vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(texts)

model = LogisticRegression()
model.fit(X, labels)

test = ["I feel very tired and weak"]
X_test = vectorizer.transform(test)

print("Prediction:", model.predict(X_test))