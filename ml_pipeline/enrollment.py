import os
import cv2
import pickle
import numpy as np
import face_recognition
from sklearn.svm import SVC

FEATURES_PATH = "ml_pipeline/face_features.pkl"
MODEL_PATH = "ml_pipeline/svm_model.pkl"

def process_new_user(name, image_path):
    print(f"Processing new authorized home user: {name}")
    image = cv2.imread(image_path)
    if image is None: return False, "Could not read image."
        
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_image)
    if len(face_locations) != 1: return False, "Upload image with exactly one face."
        
    encoding = face_recognition.face_encodings(rgb_image, face_locations)[0]
    
    if os.path.exists(FEATURES_PATH):
        with open(FEATURES_PATH, "rb") as f: data = pickle.load(f)
        X, y = list(data["X"]), list(data["y"])
    else:
        X, y = [], []
        
    X.append(encoding)
    y.append(name)
    
    with open(FEATURES_PATH, "wb") as f:
        pickle.dump({"X": np.array(X), "y": np.array(y)}, f)
        
    unique_classes = len(set(y))
    if unique_classes >= 2:
        model = SVC(kernel="linear", probability=True)
        model.fit(X, y)
        with open(MODEL_PATH, "wb") as f: pickle.dump(model, f)
        return True, "User authorized and Home Security model updated."
    return True, "User added. (Add one more for SVM to initialize)."
