import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import Database from 'better-sqlite3';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import dotenv from 'dotenv';
import { createServer } from 'http';
import { Server } from 'socket.io';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const db = new Database('database.db');
const JWT_SECRET = process.env.JWT_SECRET || 'secret';

// Initialize Database Table
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
  )
`);

const app = express();
const httpServer = createServer(app);
const io = new Server(httpServer);

app.use(express.json());

// Serve static files from 'public' folder
app.use(express.static('templates'));

// Serve index.html from root
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

// --- API ROUTES ---

app.post('/api/register', async (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ error: 'Missing username or password' });
  }

  try {
    const hashedPassword = await bcrypt.hash(password, 10);
    const stmt = db.prepare('INSERT INTO users (username, password) VALUES (?, ?)');
    stmt.run(username, hashedPassword);
    res.status(201).json({ message: 'Success' });
  } catch (err: any) {
    res.status(400).json({ error: 'Username already exists or database error.' });
  }
});

app.post('/api/login', async (req, res) => {
  const { username, password } = req.body;
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username) as any;

  if (user && await bcrypt.compare(password, user.password)) {
    const token = jwt.sign({ id: user.id, username: user.username }, JWT_SECRET, { expiresIn: '1h' });
    res.json({ token, username: user.username });
  } else {
    res.status(400).json({ error: 'Invalid username or password' });
  }
});

// --- SOCKET.IO MULTIPLAYER LOGIC ---

interface Player {
  id: string;
  username: string;
  hp: number;
  score: number;
  inMatch?: string;
  isInviting?: string;
}

const onlineUsers = new Map<string, Player>();
const matches = new Map<string, {
  p1: string;
  p2: string;
  verb?: { v1: string; v3: string };
  startTime?: number;
}>();

const VERBS = [
  { v1: "go", v3: "gone" }, { v1: "write", v3: "written" }, { v1: "buy", v3: "bought" },
  { v1: "see", v3: "seen" }, { v1: "take", v3: "taken" }, { v1: "eat", v3: "eaten" },
  { v1: "drink", v3: "drunk" }, { v1: "give", v3: "given" }, { v1: "speak", v3: "spoken" },
  { v1: "break", v3: "broken" }, { v1: "fall", v3: "fallen" }, { v1: "forget", v3: "forgotten" },
  { v1: "know", v3: "known" }, { v1: "make", v3: "made" }, { v1: "swim", v3: "swum" },
  { v1: "sing", v3: "sung" }, { v1: "begin", v3: "begun" }, { v1: "choose", v3: "chosen" },
  { v1: "fly", v3: "flown" }, { v1: "steal", v3: "stolen" }, { v1: "teach", v3: "taught" }
];

io.on('connection', (socket) => {
  console.log('User connected:', socket.id);

  socket.on('join_lobby', (username: string) => {
    onlineUsers.set(socket.id, { id: socket.id, username, hp: 100, score: 0 });
    io.emit('online_users', Array.from(onlineUsers.values()));
  });

  socket.on('challenge', (targetId: string) => {
    const challenger = onlineUsers.get(socket.id);
    const target = onlineUsers.get(targetId);
    if (challenger && target && !target.inMatch) {
      challenger.isInviting = targetId;
      io.to(targetId).emit('challenge_received', { fromId: socket.id, fromName: challenger.username });
    }
  });

  socket.on('accept_challenge', (fromId: string) => {
    const p1 = onlineUsers.get(fromId);
    const p2 = onlineUsers.get(socket.id);
    if (p1 && p2) {
      const matchId = `match_${fromId}_${socket.id}`;
      p1.inMatch = matchId;
      p2.inMatch = matchId;
      p1.hp = 100;
      p2.hp = 100;

      matches.set(matchId, { p1: fromId, p2: socket.id });

      socket.join(matchId);
      io.sockets.sockets.get(fromId)?.join(matchId);

      io.to(matchId).emit('match_start', { 
        matchId, 
        p1: { id: p1.id, username: p1.username }, 
        p2: { id: p2.id, username: p2.username } 
      });

      sendNewVerb(matchId);
    }
  });

  socket.on('submit_answer', (answer: string) => {
    const player = onlineUsers.get(socket.id);
    if (player && player.inMatch) {
      const match = matches.get(player.inMatch);
      if (match && match.verb && answer.toLowerCase() === match.verb.v3.toLowerCase()) {
        const opponentId = match.p1 === socket.id ? match.p2 : match.p1;
        const opponent = onlineUsers.get(opponentId);
        
        if (opponent) {
          opponent.hp -= 20;
          io.to(player.inMatch).emit('match_update', {
            winner: socket.id,
            p1: onlineUsers.get(match.p1),
            p2: onlineUsers.get(match.p2)
          });

          if (opponent.hp <= 0) {
            io.to(player.inMatch).emit('match_end', { winner: player.username });
            matchEnd(player.inMatch);
          } else {
            sendNewVerb(player.inMatch);
          }
        }
      }
    }
  });

  function sendNewVerb(matchId: string) {
    const match = matches.get(matchId);
    if (match) {
      const verb = VERBS[Math.floor(Math.random() * VERBS.length)];
      match.verb = verb;
      io.to(matchId).emit('new_verb', verb.v1);
    }
  }

  function matchEnd(matchId: string) {
    const match = matches.get(matchId);
    if (match) {
      const p1 = onlineUsers.get(match.p1);
      const p2 = onlineUsers.get(match.p2);
      if (p1) p1.inMatch = undefined;
      if (p2) p2.inMatch = undefined;
      matches.delete(matchId);
      io.emit('online_users', Array.from(onlineUsers.values()));
    }
  }

  socket.on('disconnect', () => {
    const player = onlineUsers.get(socket.id);
    if (player?.inMatch) {
      io.to(player.inMatch).emit('match_end', { winner: 'Opponent (Disconnected)' });
      matchEnd(player.inMatch);
    }
    onlineUsers.delete(socket.id);
    io.emit('online_users', Array.from(onlineUsers.values()));
    console.log('User disconnected:', socket.id);
  });
});

// Listen on Port
const PORT = process.env.PORT || 3000;
httpServer.listen(PORT, '0.0.0.0', () => {
  console.log(`Server is running on http://0.0.0.0:${PORT}`);
});
