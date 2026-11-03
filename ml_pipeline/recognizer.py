import cv2
import face_recognition
import pickle
import numpy as np
import os

MODEL_PATH = "ml_pipeline/svm_model.pkl"

def generate_frames():
    svm_model = None
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            svm_model = pickle.load(f)

    cap = cv2.VideoCapture(0)
    
    while True:
        success, frame = cap.read()
        if not success:
            break
            
        small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        face_locations = face_recognition.face_locations(rgb_small_frame)
        
        if face_locations and svm_model:
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
            
            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                preds = svm_model.predict_proba([face_encoding])[0]
                best_class_index = np.argmax(preds)
                best_prob = preds[best_class_index]
                
                # Threshold for Identifying Home Owners vs Unknown
                if best_prob > 0.65:
                    name = svm_model.classes_[best_class_index]
                    color = (162, 224, 93)  # Green
                else:
                    name = "Unknown Visitor"
                    color = (139, 127, 255) # Red
                    
                top *= 2
                right *= 2
                bottom *= 2
                left *= 2
                
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.rectangle(frame, (left, bottom - 30), (right, bottom), color, cv2.FILLED)
                cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.6, (0,0,0), 1)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
