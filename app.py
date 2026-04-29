from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__)

# Create the database and user table
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
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

@app.route('/unit1.html')
def unit1_page():
    return render_template('unit1.html')

@app.route('/unit2.html')
def unit2_page():
    return render_template('unit2.html')

@app.route('/unit3.html')
def unit3_page():
    return render_template('unit3.html')

@app.route('/unit4.html')
def unit4_page():
    return render_template('unit4.html')

@app.route('/unit5.html')
def unit5_page():
    return render_template('unit5.html')

@app.route('/unit6.html')
def unit6_page():
    return render_template('unit6.html')

@app.route('/unit7.html')
def unit7_page():
    return render_template('unit7.html')

@app.route('/unit8.html')
def unit8_page():
    return render_template('unit8.html')

@app.route('/unit9.html')
def unit9_page():
    return render_template('unit9.html')

@app.route('/unit10.html')
def unit10_page():
    return render_template('unit10.html')

@app.route('/duel.html')
def duel_page():
    return render_template('duel.html')


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                       (data['username'], data['password']))
        conn.commit()
        conn.close()
        return jsonify({"message": "Success"}), 201
    except:
        return jsonify({"error": "User already exists"}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", 
                   (data['username'], data['password']))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return jsonify({"username": data['username'], "token": "ok"}), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
