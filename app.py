import os
import sqlite3
import random
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# threading mode is safer when C extensions or newer Python versions fail with eventlet
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=True, engineio_logger=True)

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
matches = {} # room_id: {p1: {id, username, hp}, p2: {id, username, hp}, current_verb}

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

@app.route('/duel.html')
def duel_page():
    return render_template('duel.html')


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

# Socket events
@socketio.on('connect')
def handle_connect():
    print(f"User connected: {request.sid}")

@socketio.on('create_room')
def handle_create_room(username):
    room_id = str(random.randint(1000, 9999))
    while room_id in matches:
        room_id = str(random.randint(1000, 9999))
    
    matches[room_id] = {
        "p1": {"id": request.sid, "username": username, "hp": 100},
        "p2": None,
        "current_verb": random.choice(VERBS)
    }
    join_room(room_id)
    print(f"Room Created: {room_id} by {username} ({request.sid})")
    # Using emit directly to sender
    emit('room_created', room_id, room=request.sid)

@socketio.on('cancel_room')
def handle_cancel_room(room_id):
    room_id = str(room_id)
    if room_id in matches:
        if matches[room_id]['p1']['id'] == request.sid:
            del matches[room_id]
            leave_room(room_id)
            print(f"Room Cancelled: {room_id}")

@socketio.on('join_room_code')
def handle_join_room(data):
    room_id = str(data['code']).strip()
    username = data['username']
    
    print(f"Attempting to join room: {room_id} by {username} ({request.sid})")
    
    if room_id in matches:
        if matches[room_id]['p2'] is None:
            matches[room_id]['p2'] = {"id": request.sid, "username": username, "hp": 100}
            join_room(room_id)
            
            match_data = {
                "matchId": room_id,
                "p1": matches[room_id]['p1'],
                "p2": matches[room_id]['p2']
            }
            emit('match_start', match_data, room=room_id)
            emit('new_verb', matches[room_id]["current_verb"]["v1"], room=room_id)
            print(f"Match Started in room {room_id}")
        else:
            emit('error', 'Bu oda zaten dolu.', to=request.sid)
    else:
        emit('error', 'Oda bulunamadı. Kodu kontrol edin.', to=request.sid)

@socketio.on('submit_answer')
def handle_submit_answer(answer):
    # Find match for this sid
    match_id = None
    for mid, mdata in matches.items():
        if mdata.get("p1") and mdata["p1"]["id"] == request.sid:
            match_id = mid
            break
        if mdata.get("p2") and mdata["p2"]["id"] == request.sid:
            match_id = mid
            break
    
    if not match_id:
        return

    match = matches[match_id]
    correct_v3 = match["current_verb"]["v3"].lower()
    
    if answer.lower() == correct_v3:
        attacker_id = request.sid
        # Damage opponent
        if match["p1"]["id"] == attacker_id:
            match["p2"]["hp"] -= 10
        else:
            match["p1"]["hp"] -= 10
        
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
