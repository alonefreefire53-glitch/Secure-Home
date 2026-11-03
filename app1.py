from flask import Flask, render_template, request, redirect, url_for, Response, jsonify, session, send_from_directory
import os
import cv2
import pickle
import numpy as np
import face_recognition
from sklearn.svm import SVC
import mysql.connector
from datetime import datetime
import base64
import smtplib
from email.message import EmailMessage
import threading
import time

app = Flask(__name__, static_url_path='', static_folder='static', template_folder='templates')
app.secret_key = 'securehome_admin_secret_key'

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Ensure directories exist
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
COLLECTED_DIR = os.path.join(BASE_DIR, 'CollectedImages')
os.makedirs(COLLECTED_DIR, exist_ok=True)

# ================= EMAIL CONFIGURATION =================
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SENDER_EMAIL = 'alonefree53@gmail.com'
SENDER_PASSWORD = 'bjsm hjkl jyli txhv'
RECEIVER_EMAIL = 'hello@gmail.com'

@app.route('/CollectedImages/<path:filename>')
def serve_collected_images(filename):
    return send_from_directory(COLLECTED_DIR, filename)

def _send_email_thread(image_path, capture_time):
    try:
        clean_password = SENDER_PASSWORD.replace(" ", "").strip()
        sender = SENDER_EMAIL.strip()
        receiver = RECEIVER_EMAIL.strip()

        msg = EmailMessage()
        msg['Subject'] = '🚨 SECURITY ALERT: Unknown Visitor Detected!'
        msg['From'] = sender
        msg['To'] = receiver
        msg['Set-content'] = (
            f'SecureHome Alert!\n\n'
            f'Camera par ek Unknown Visitor detect hua hai.\n'
            f'Time: {capture_time}\n\n'
            f'Captured photo is email ke saath attached hai.'
        )
        msg.set_content(
            f'SecureHome Alert!\n\n'
            f'Camera par ek Unknown Visitor detect hua hai.\n'
            f'Time: {capture_time}\n\n'
            f'Captured photo is email ke saath attached hai.'
        )

        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                file_data = f.read()
                file_name = os.path.basename(image_path)
            msg.add_attachment(file_data, maintype='image', subtype='jpeg', filename=file_name)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, clean_password)
            server.send_message(msg)
        print(f'📧 Alert email successfully bhej diya gaya -> {receiver}!')
    except Exception as e:
        print(f'❌ Email bhejne mein error aaya: {e}')

def send_alert_email(image_path, capture_time):
    t = threading.Thread(target=_send_email_thread, args=(image_path, capture_time), daemon=True)
    t.start()

# ================= DATABASE SETUP =================
def init_db():
    try:
        db = mysql.connector.connect(host='localhost', user='root', password='open')
        cursor = db.cursor()
        cursor.execute('CREATE DATABASE IF NOT EXISTS face_security')
        cursor.execute('USE face_security')
        
        # Base Admins table
        cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
            admin_id INT AUTO_INCREMENT PRIMARY KEY,
            admin_name VARCHAR(100) NOT NULL UNIQUE,
            email VARCHAR(100),
            password VARCHAR(100)
        )''')
        db.commit()

        # Default admin insert
        cursor.execute("SELECT COUNT(*) FROM admins WHERE admin_name = 'admin'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO admins (admin_name, email, password) VALUES ('admin', 'admin@securehome.com', 'admin123')")
            db.commit()

        cursor.close()
        db.close()
        print('✅ Database initialized successfully!')
    except Exception as e:
        print(f'❌ Error initializing database: {e}')

# Naye admin ke tables dynamically create karne ke liye helper function
def ensure_admin_tables(admin_name):
    try:
        db = get_db()
        if db:
            cursor = db.cursor()
            safe_admin = admin_name.strip().replace(' ', '_')
            
            cursor.execute(f'''CREATE TABLE IF NOT EXISTS `{safe_admin}_authorized_users` (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                role VARCHAR(50),
                email VARCHAR(100),
                photo_path VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            
            cursor.execute(f'''CREATE TABLE IF NOT EXISTS `{safe_admin}_unknown_alerts` (
                id INT AUTO_INCREMENT PRIMARY KEY,
                image_path VARCHAR(255),
                status VARCHAR(20) DEFAULT 'New',
                capture_time DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            
            cursor.execute(f'''CREATE TABLE IF NOT EXISTS `{safe_admin}_security_logs` (
                log_id INT AUTO_INCREMENT PRIMARY KEY,
                person_name VARCHAR(100),
                event_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                event_type VARCHAR(50),
                details TEXT
            )''')
            db.commit()
            cursor.close()
            db.close()
    except Exception as e:
        print(f'❌ Error creating tables for admin {admin_name}: {e}')
def get_db():
    try:
        return mysql.connector.connect(host='localhost', user='root', password='open', database='face_security')
    except Exception as e:
        print(f'❌ Database connection error: {e}')
        return None

def get_admin_paths(admin_name):
    safe_admin = admin_name.strip().replace(' ', '_')
    admin_folder = os.path.join(COLLECTED_DIR, safe_admin)
    os.makedirs(admin_folder, exist_ok=True)
    features_path = os.path.join(admin_folder, f'{safe_admin}_face_features.pkl')
    model_path = os.path.join(admin_folder, f'{safe_admin}_svm_model.pkl')
    return admin_folder, features_path, model_path

# ================= SVM TRAINING & RETRAINING =================
def retrain_svm_model(admin_name):
    _, features_path, model_path = get_admin_paths(admin_name)
    if not os.path.exists(features_path):
        return
    with open(features_path, 'rb') as f:
        data = pickle.load(f)
    X, y = list(data['X']), list(data['y'])
    
    unique_classes = len(set(y))
    if len(X) > 0 and unique_classes >= 2:
        model = SVC(kernel='linear', probability=True)
        model.fit(X, y)
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        print(f'✅ SVM Model for [{admin_name}] successfully retrained with {unique_classes} classes: {set(y)}')
    else:
        if os.path.exists(model_path):
            os.remove(model_path)
        print(f'⚠️ SVM for [{admin_name}] needs at least 2 different users (Current unique users: {unique_classes}).')

def process_bulk_enrollment(admin_name, name, image_paths):
    print(f'Processing {len(image_paths)} images for user {name} under admin {admin_name}...')
    new_X, new_y = [], []
    
    for path in image_paths:
        image = cv2.imread(path)
        if image is None:
            continue
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_image, model='hog')
        
        if len(face_locations) >= 1:
            encoding = face_recognition.face_encodings(rgb_image, [face_locations[0]])[0]
            new_X.append(encoding)
            new_y.append(name)
    
    if not new_X:
        return False, 'No valid faces found in the captured images.'
    
    _, features_path, _ = get_admin_paths(admin_name)
    if os.path.exists(features_path):
        with open(features_path, 'rb') as f:
            data = pickle.load(f)
        X, y = list(data['X']), list(data['y'])
    else:
        X, y = [], []
        
    X.extend(new_X)
    y.extend(new_y)
    
    with open(features_path, 'wb') as f:
        pickle.dump({'X': np.array(X), 'y': np.array(y)}, f)
        
    retrain_svm_model(admin_name)
    return True, 'User authorized and SVM model updated.'

# ================= HYBRID VIDEO RECOGNITION =================
def generate_frames(admin_name):
    _, features_path, model_path = get_admin_paths(admin_name)
    safe_admin = admin_name.strip().replace(' ', '_')
    
    svm_model = None
    known_X, known_y = np.array([]), np.array([])
    last_model_mtime = 0
    last_features_mtime = 0
    last_logged_time = {}

    def load_data():
        nonlocal svm_model, known_X, known_y, last_model_mtime, last_features_mtime
        if os.path.exists(features_path):
            mtime = os.path.getmtime(features_path)
            if mtime > last_features_mtime:
                last_features_mtime = mtime
                with open(features_path, 'rb') as f:
                    data = pickle.load(f)
                    known_X = np.array(data['X'])
                    known_y = np.array(data['y'])
        if os.path.exists(model_path):
            mtime = os.path.getmtime(model_path)
            if mtime > last_model_mtime:
                last_model_mtime = mtime
                with open(model_path, 'rb') as f:
                    svm_model = pickle.load(f)

    load_data()
    cap = cv2.VideoCapture(0)
    unknown_counter = 0
    cooldown = 0
    
    try:
        while True:
            success, frame = cap.read()
            if not success:
                break
                
            load_data()
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_small_frame)
            
            if cooldown > 0:
                cooldown -= 1
                
            if face_locations:
                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

                for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                    name = 'Unknown Visitor'
                    color = (139, 127, 255) # Red for Unknown
                    
                    if len(known_X) > 0:
                        distances = face_recognition.face_distance(known_X, face_encoding)
                        best_match_idx = np.argmin(distances)
                        min_dist = distances[best_match_idx]
                        
                        if min_dist < 0.55:
                            if svm_model is not None:
                                preds = svm_model.predict_proba([face_encoding])[0]
                                best_class_idx = np.argmax(preds)
                                if preds[best_class_idx] > 0.45:
                                    name = str(svm_model.classes_[best_class_idx])
                                else:
                                    name = str(known_y[best_match_idx])
                            else:
                                name = str(known_y[best_match_idx])
                                
                            color = (162, 224, 93) # Green for Authorized
                            unknown_counter = 0

                            current_time = time.time()
                            if name not in last_logged_time or (current_time - last_logged_time[name]) > 15:
                                last_logged_time[name] = current_time
                                db = get_db()
                                if db:
                                    cursor = db.cursor()
                                    cursor.execute(
                                        f'INSERT INTO `{safe_admin}_security_logs` (person_name, event_type, details) VALUES (%s, %s, %s)', 
                                        (name, 'Authorized', f'Authorized user {name} detected successfully at entrance')
                                    )
                                    db.commit()
                                    cursor.close()
                                    db.close()
                        else:
                            unknown_counter += 1
                    else:
                        unknown_counter += 1
                        
                    top *= 2; right *= 2; bottom *= 2; left *= 2
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    cv2.rectangle(frame, (left, bottom - 30), (right, bottom), color, cv2.FILLED)
                    cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0,0,0), 1)

                    if unknown_counter >= 15 and cooldown == 0:
                        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f'Unknown_{timestamp_str}.jpg'
                        rel_img_path = f'CollectedImages/{safe_admin}/{filename}'
                        abs_img_path = os.path.join(COLLECTED_DIR, safe_admin, filename)
                        
                        cv2.imwrite(abs_img_path, frame)
                        
                        db = get_db()
                        if db:
                            cursor = db.cursor()
                            cursor.execute(f'INSERT INTO `{safe_admin}_unknown_alerts` (image_path) VALUES (%s)', (rel_img_path,))
                            cursor.execute(f'INSERT INTO `{safe_admin}_security_logs` (person_name, event_type, details) VALUES (%s, %s, %s)', 
                                           ('Unknown', 'Alert', 'Unknown visitor detected and photo captured'))
                            db.commit()
                            cursor.close()
                            db.close()
                        
                        capture_dt = datetime.now().strftime('%b %d, %Y %H:%M:%S')
                        send_alert_email(abs_img_path, capture_dt)

                        unknown_counter = 0
                        cooldown = 120

            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    finally:
        cap.release()

# ================= WEB ROUTES =================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = get_db()
        if db:
            cursor = db.cursor()
            cursor.execute('SELECT admin_name, password FROM admins WHERE admin_name = %s', (username,))
            admin = cursor.fetchone()
            db.close()
            
            if admin and admin[1] == password:
                session['admin_logged_in'] = True
                session['admin_name'] = admin[0]
                return redirect(url_for('dashboard'))
        
        error = 'Incorrect credentials. Try admin / admin123'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_name', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    admin_name = session.get('admin_name')
    safe_admin = admin_name.strip().replace(' ', '_')
    db = get_db()
    user_count, alert_count, log_count, recent_logs = 0, 0, 0, []
    
    if db:
        cursor = db.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM `{safe_admin}_authorized_users`')
        user_count = cursor.fetchone()[0]
        cursor.execute(f'SELECT COUNT(*) FROM `{safe_admin}_unknown_alerts`')
        alert_count = cursor.fetchone()[0]
        cursor.execute(f'SELECT COUNT(*) FROM `{safe_admin}_security_logs`')
        log_count = cursor.fetchone()[0]
        cursor.execute(f"SELECT person_name, DATE_FORMAT(event_time, '%b %d, %Y %H:%i'), event_type, details FROM `{safe_admin}_security_logs` ORDER BY event_time DESC LIMIT 5")
        for row in cursor.fetchall():
            recent_logs.append({'person': row[0], 'time': row[1], 'type': row[2], 'details': row[3]})
        db.close()
        
    return render_template('dashboard.html', user_count=user_count, unknown_count=alert_count, event_count=log_count, recent_logs=recent_logs)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    success = None
    if request.method == 'POST':
        username = request.form.get('username').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        
        if not username or not password:
            error = 'Username aur Password bharna zaroori hai!'
        else:
            db = get_db()
            if db:
                cursor = db.cursor()
                # Check karo ki admin pehle se exist karta hai kya
                cursor.execute('SELECT COUNT(*) FROM admins WHERE admin_name = %s', (username,))
                if cursor.fetchone()[0] > 0:
                    error = 'Ye admin username pehle se taken hai. Doosra try karo!'
                else:
                    # Naya admin insert karo
                    cursor.execute('INSERT INTO admins (admin_name, email, password) VALUES (%s, %s, %s)', (username, email, password))
                    db.commit()
                    cursor.close()
                    db.close()
                    
                    # Naye admin ke tables aur folders turant create karo
                    ensure_admin_tables(username)
                    get_admin_paths(username)
                    
                    success = 'Registration successful! Ab aap login kar sakte hain.'
    return render_template('register.html', error=error, success=success)

@app.route('/camera')
def camera():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    return render_template('camera.html')

@app.route('/users')
def users():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    admin_name = session.get('admin_name')
    safe_admin = admin_name.strip().replace(' ', '_')
    db = get_db()
    users_list = []
    
    if db:
        cursor = db.cursor()
        cursor.execute(f'SELECT id, name, role, email, photo_path FROM `{safe_admin}_authorized_users` ORDER BY created_at DESC')
        for row in cursor.fetchall():
            photo = row[4].replace('\\', '/') if row[4] else ''
            if photo and not photo.startswith('/'):
                photo = '/' + photo
            users_list.append({'id': row[0], 'name': row[1], 'role': row[2], 'email': row[3], 'photo_path': photo})
        db.close()
    return render_template('users.html', users=users_list)

@app.route('/alerts')
def alerts():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    admin_name = session.get('admin_name')
    safe_admin = admin_name.strip().replace(' ', '_')
    db = get_db()
    alerts_list = []
    
    if db:
        cursor = db.cursor()
        cursor.execute(f"SELECT id, image_path, DATE_FORMAT(capture_time, '%b %d, %Y %H:%i'), status FROM `{safe_admin}_unknown_alerts` ORDER BY capture_time DESC")
        for row in cursor.fetchall():
            img_path = row[1].replace('\\', '/') if row[1] else ''
            if img_path and not img_path.startswith('/'):
                img_path = '/' + img_path
            alerts_list.append({'id': row[0], 'image_path': img_path, 'time': row[2], 'status': row[3]})
        db.close()
    return render_template('alerts.html', alerts=alerts_list)

@app.route('/logs')
def logs():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    admin_name = session.get('admin_name')
    safe_admin = admin_name.strip().replace(' ', '_')
    db = get_db()
    logs_list = []
    
    if db:
        cursor = db.cursor()
        cursor.execute(f"SELECT person_name, DATE_FORMAT(event_time, '%b %d, %Y %H:%i'), event_type, details FROM `{safe_admin}_security_logs` ORDER BY event_time DESC")
        for row in cursor.fetchall():
            logs_list.append({'person': row[0], 'time': row[1], 'type': row[2], 'details': row[3]})
        db.close()
    return render_template('logs.html', logs=logs_list)

@app.route('/api/video_feed')
def video_feed():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    admin_name = session.get('admin_name')
    return Response(generate_frames(admin_name), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/upload_frame', methods=['POST'])
def upload_frame():
    if not session.get('admin_logged_in'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    admin_name = session.get('admin_name')
    safe_admin = admin_name.strip().replace(' ', '_')
    data = request.get_json()
    name = data.get('name')
    frame_idx = data.get('frame_idx')
    photo_b64 = data.get('photo_base64')
    
    if not name or not photo_b64:
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400
        
    safe_user = name.strip().replace(' ', '_')
    admin_folder, _, _ = get_admin_paths(admin_name)
    user_dir = os.path.join(admin_folder, safe_user)
    os.makedirs(user_dir, exist_ok=True)
    
    _, encoded = photo_b64.split(',', 1)
    image_data = base64.b64decode(encoded)
    
    photo_path = os.path.join(user_dir, f'capture_{frame_idx}.jpg')
    with open(photo_path, 'wb') as f:
        f.write(image_data)
        
    return jsonify({'status': 'success'})

@app.route('/api/add_user', methods=['POST'])
def add_user():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    admin_name = session.get('admin_name')
    safe_admin = admin_name.strip().replace(' ', '_')
    name = request.form.get('name')
    role = request.form.get('role')
    email = request.form.get('email')
    
    if name:
        safe_user = name.strip().replace(' ', '_')
        admin_folder, _, _ = get_admin_paths(admin_name)
        user_dir = os.path.join(admin_folder, safe_user)
        
        if os.path.exists(user_dir):
            saved_files = sorted([f for f in os.listdir(user_dir) if f.endswith('.jpg')])
            saved_paths = [os.path.join(user_dir, f) for f in saved_files]
            
            if saved_paths:
                process_bulk_enrollment(admin_name, name, saved_paths)
                rel_photo_path = f'CollectedImages/{safe_admin}/{safe_user}/{saved_files[0]}'
                
                db = get_db()
                if db:
                    cursor = db.cursor()
                    cursor.execute(f'INSERT INTO `{safe_admin}_authorized_users` (name, role, email, photo_path) VALUES (%s, %s, %s, %s)', 
                                   (name, role, email, rel_photo_path))
                    cursor.execute(f'INSERT INTO `{safe_admin}_security_logs` (person_name, event_type, details) VALUES (%s, %s, %s)', 
                                   (name, 'Authorized', 'Profile enrolled & trained via webcam'))
                    db.commit()
                    cursor.close()
                    db.close()
                    
    return redirect(url_for('users', added=True))

@app.route('/api/resolve_alert/<int:alert_id>')
def resolve_alert(alert_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    admin_name = session.get('admin_name')
    safe_admin = admin_name.strip().replace(' ', '_')
    db = get_db()
    if db:
        cursor = db.cursor()
        cursor.execute(f"UPDATE `{safe_admin}_unknown_alerts` SET status = 'Resolved' WHERE id = %s", (alert_id,))
        cursor.execute(f'INSERT INTO `{safe_admin}_security_logs` (person_name, event_type, details) VALUES (%s, %s, %s)', 
                       ('System', 'Admin Action', f'Alert #{alert_id} resolved'))
        db.commit()
        db.close()
    return redirect(url_for('alerts'))

@app.route('/api/delete_user/<int:user_id>')
def delete_user(user_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    admin_name = session.get('admin_name')
    safe_admin = admin_name.strip().replace(' ', '_')
    db = get_db()
    
    if db:
        cursor = db.cursor()
        cursor.execute(f'SELECT name FROM `{safe_admin}_authorized_users` WHERE id = %s', (user_id,))
        user = cursor.fetchone()
        if user:
            user_name = user[0]
            cursor.execute(f'DELETE FROM `{safe_admin}_authorized_users` WHERE id = %s', (user_id,))
            cursor.execute(f'INSERT INTO `{safe_admin}_security_logs` (person_name, event_type, details) VALUES (%s, %s, %s)', 
                           (user_name, 'Admin Action', 'User removed from authorized list'))
            db.commit()
            
            _, features_path, model_path = get_admin_paths(admin_name)
            if os.path.exists(features_path):
                with open(features_path, 'rb') as f:
                    data = pickle.load(f)
                X, y = list(data['X']), list(data['y'])
                
                filtered = [(x_item, y_item) for x_item, y_item in zip(X, y) if y_item != user_name]
                if filtered:
                    new_X = np.array([item[0] for item in filtered])
                    new_y = np.array([item[1] for item in filtered])
                    with open(features_path, 'wb') as f:
                        pickle.dump({'X': new_X, 'y': new_y}, f)
                else:
                    if os.path.exists(features_path): os.remove(features_path)
                    if os.path.exists(model_path): os.remove(model_path)
                
                retrain_svm_model(admin_name)
        db.close()
    return redirect(url_for('users'))

@app.route('/api/check_session')
def check_session():
    if not session.get('admin_logged_in'):
        return jsonify({'status': 'unauthorized'}), 401
    return jsonify({'status': 'authorized'}), 200

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)