import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
import os
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Irregular Verbs for Duel
VERBS = [
    {"v1": "go", "v3": "gone"},
    {"v1": "eat", "v3": "eaten"},
    {"v1": "see", "v3": "seen"},
    {"v1": "do", "v2": "did", "v3": "done"},
    {"v1": "take", "v3": "taken"},
    {"v1": "give", "v3": "given"},
    {"v1": "write", "v3": "written"},
    {"v1": "speak", "v3": "spoken"},
    {"v1": "break", "v3": "broken"},
    {"v1": "choose", "v3": "chosen"},
    {"v1": "drive", "v3": "driven"},
    {"v1": "forget", "v3": "forgotten"},
    {"v1": "know", "v3": "known"},
    {"v1": "sing", "v3": "sung"},
    {"v1": "drink", "v3": "drunk"},
    {"v1": "swim", "v3": "swum"},
]

# Game State
online_users = {} # id: {username, id}
matches = {} # room_id: {p1: {id, username, hp}, p2: {id, username, hp}, current_verb}

# Create the database and user table
def init_db():
    conn = sqlite3.connect('database.db', timeout=20)
    try:
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

@app.route('/duel.html')
def duel_page():
    return render_template('duel.html')


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    conn = sqlite3.connect('database.db', timeout=20)
    try:
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
    conn = sqlite3.connect('database.db', timeout=20)
    try:
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

# Socket events
@socketio.on('connect')
def handle_connect():
    print(f"User connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in online_users:
        del online_users[request.sid]
        emit_online_users()

def emit_online_users():
    emit('online_users', list(online_users.values()), broadcast=True)

@socketio.on('join_lobby')
def handle_join_lobby(username):
    online_users[request.sid] = {"id": request.sid, "username": username}
    emit_online_users()

@socketio.on('challenge')
def handle_challenge(target_id):
    if target_id in online_users:
        emit('challenge_received', {
            "fromId": request.sid,
            "fromName": online_users[request.sid]["username"]
        }, room=target_id)

@socketio.on('accept_challenge')
def handle_accept_challenge(challenger_id):
    if challenger_id not in online_users or request.sid not in online_users:
        return

    room_id = f"match_{random.randint(1000, 9999)}"
    p1 = online_users[challenger_id]
    p2 = online_users[request.sid]

    match_data = {
        "matchId": room_id,
        "p1": {"id": p1["id"], "username": p1["username"], "hp": 100},
        "p2": {"id": p2["id"], "username": p2["username"], "hp": 100},
        "current_verb": random.choice(VERBS)
    }
    matches[room_id] = match_data

    join_room(room_id, sid=challenger_id)
    join_room(room_id, sid=request.sid)

    emit('match_start', match_data, room=room_id)
    emit('new_verb', match_data["current_verb"]["v1"], room=room_id)

@socketio.on('submit_answer')
def handle_submit_answer(answer):
    # Find match for this sid
    match_id = None
    for mid, mdata in matches.items():
        if mdata["p1"]["id"] == request.sid or mdata["p2"]["id"] == request.sid:
            match_id = mid
            break
    
    if not match_id:
        return

    match = matches[match_id]
    correct_v3 = match["current_verb"]["v3"].lower()
    
    if answer.lower() == correct_v3:
        # Damage opponent
        attacker_id = request.sid
        if match["p1"]["id"] == attacker_id:
            match["p2"]["hp"] -= 10
        else:
            match["p1"]["hp"] -= 10
        
        # Check for win
        if match["p1"]["hp"] <= 0 or match["p2"]["hp"] <= 0:
            winner_name = match["p1"]["username"] if match["p2"]["hp"] <= 0 else match["p2"]["username"]
            emit('match_update', {**match, "attacker_id": attacker_id}, room=match_id)
            emit('match_end', {"winner": winner_name}, room=match_id)
            del matches[match_id]
        else:
            emit('match_update', {**match, "attacker_id": attacker_id}, room=match_id)
            match["current_verb"] = random.choice(VERBS)
            emit('new_verb', match["current_verb"]["v1"], room=match_id)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    socketio.run(app, debug=False, host='0.0.0.0', port=port)
