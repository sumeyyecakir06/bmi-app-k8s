from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import hashlib
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'gizli-anahtar-bmi-projesi-2026')

db_path = os.environ.get('DB_PATH', '/app/data/bmi.db')

def get_db():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bmi_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            weight REAL NOT NULL,
            height REAL NOT NULL,
            bmi REAL NOT NULL,
            category TEXT NOT NULL,
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def calculate_bmi(weight, height):
    height_m = height / 100
    bmi = weight / (height_m ** 2)
    
    if bmi < 18.5:
        category = "Aşırı Zayıf"
    elif bmi < 25:
        category = "Normal"
    elif bmi < 30:
        category = "Aşırı Kilolu"
    else:
        category = "Obezite"
    
    return round(bmi, 1), category

init_db()

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        
        if password != confirm:
            return "Şifreler eşleşmiyor!", 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return "Bu e-posta zaten kayıtlı!", 400
        
        hashed = hash_password(password)
        cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed))
        conn.commit()
        conn.close()
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if not user or user['password'] != hash_password(password):
            return "Geçersiz e-posta veya şifre!", 400
        
        session['user_id'] = user['id']
        session['user_email'] = user['email']
        
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT weight, height, bmi, category, calculated_at 
        FROM bmi_history 
        WHERE user_id = ? 
        ORDER BY calculated_at DESC 
        LIMIT 10
    """, (session['user_id'],))
    history = cursor.fetchall()
    conn.close()
    
    return render_template('dashboard.html', history=history)

@app.route('/calculate', methods=['POST'])
def calculate():
    if 'user_id' not in session:
        return jsonify({"error": "Giriş yapmalısınız"}), 401
    
    weight = float(request.form.get('weight'))
    height = float(request.form.get('height'))
    
    bmi, category = calculate_bmi(weight, height)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bmi_history (user_id, weight, height, bmi, category)
        VALUES (?, ?, ?, ?, ?)
    """, (session['user_id'], weight, height, bmi, category))
    conn.commit()
    conn.close()
    
    return jsonify({
        "bmi": bmi,
        "category": category
    })

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        conn = get_db()
        cursor = conn.cursor()
        
        if action == 'update_email':
            new_email = request.form.get('email')
            cursor.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, session['user_id']))
            session['user_email'] = new_email
            conn.commit()
        
        elif action == 'change_password':
            current = request.form.get('current_password')
            new_pass = request.form.get('new_password')
            confirm = request.form.get('confirm_password')
            
            cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
            user = cursor.fetchone()
            
            if user['password'] != hash_password(current):
                conn.close()
                return "Mevcut şifre yanlış!", 400
            if new_pass != confirm:
                conn.close()
                return "Yeni şifreler eşleşmiyor!", 400
            
            cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hash_password(new_pass), session['user_id']))
            conn.commit()
        
        conn.close()
        return redirect(url_for('profile'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT email, created_at FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    return render_template('profile.html', user=user)

@app.route('/health')
def health():
    return {"status": "healthy", "database": "connected"}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
