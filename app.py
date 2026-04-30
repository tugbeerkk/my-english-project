import os
import sqlite3
import random
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

# Create the database and user table
def init_db():
    conn = sqlite3.connect('database.db', timeout=30)
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.commit()
    finally:
        conn.close()

init_db()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login.html')
def login_page():
    return render_template('login.html')

@app.route('/register.html')
def register_page():
    return render_template('register.html')

# Routes for units
@app.route('/unit<int:n>.html')
def unit_page(n):
    if 1 <= n <= 10:
        return render_template(f'unit{n}.html')
    return "Not Found", 404

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    conn = sqlite3.connect('database.db', timeout=30)
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                       (data['username'], data['password']))
        conn.commit()
        return jsonify({"message": "Success"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "User already exists"}), 400
    except Exception as e:
        print(f"Register Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = sqlite3.connect('database.db', timeout=30)
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", 
                       (data['username'], data['password']))
        user = cursor.fetchone()
        if user:
            return jsonify({"username": data['username'], "token": "ok"}), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 400
    finally:
        conn.close()

@app.route('/healthz')
def healthz():
    return jsonify({"status": "ready"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    app.run(debug=False, host='0.0.0.0', port=port)
