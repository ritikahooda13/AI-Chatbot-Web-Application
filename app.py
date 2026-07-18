from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import requests
import sqlite3
import os
import base64
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sqrock-ai-chatbot-secret-key-change-this')

DB_PATH = os.path.join(os.path.dirname(__file__), 'chatbot.db')


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
    ''')
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('register.html', error="Username and password are required.")

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username = ?', (username,))
        if c.fetchone():
            conn.close()
            return render_template('register.html', error="Username already exists.")

        c.execute(
            'INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)',
            (username, generate_password_hash(password), datetime.now().isoformat())
        )
        conn.commit()
        user_id = c.lastrowid
        conn.close()

        session['user_id'] = user_id
        session['username'] = username
        return redirect(url_for('home'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('home'))

        return render_template('login.html', error="Invalid username or password.")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Main app routes
# ---------------------------------------------------------------------------
@app.route('/')
@login_required
def home():
    return render_template('index.html', username=session.get('username'))


@app.route('/conversations', methods=['GET'])
@login_required
def get_conversations():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        'SELECT id, title, created_at FROM conversations WHERE user_id = ? ORDER BY id DESC',
        (session['user_id'],)
    )
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/conversation/<int:conv_id>', methods=['GET'])
@login_required
def get_conversation(conv_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM conversations WHERE id = ? AND user_id = ?', (conv_id, session['user_id']))
    conv = c.fetchone()
    if not conv:
        conn.close()
        return jsonify({'error': 'Not found'}), 404

    c.execute('SELECT sender, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY id ASC', (conv_id,))
    messages = c.fetchall()
    conn.close()
    return jsonify({'messages': [dict(m) for m in messages]})


@app.route('/conversation/<int:conv_id>', methods=['DELETE'])
@login_required
def delete_conversation(conv_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM conversations WHERE id = ? AND user_id = ?', (conv_id, session['user_id']))
    c.execute('DELETE FROM messages WHERE conversation_id = ?', (conv_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/new_conversation', methods=['POST'])
@login_required
def new_conversation():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        'INSERT INTO conversations (user_id, title, created_at) VALUES (?, ?, ?)',
        (session['user_id'], 'New Chat', datetime.now().isoformat())
    )
    conn.commit()
    conv_id = c.lastrowid
    conn.close()
    return jsonify({'conversation_id': conv_id})


@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    filename = file.filename or 'file'
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if ext == 'pdf':
        try:
            from pypdf import PdfReader
            reader = PdfReader(file.stream)
            text = ''
            for page in reader.pages[:25]:
                text += (page.extract_text() or '') + '\n'
            text = text.strip()
            if not text:
                text = '(No readable text found in this PDF — it may be a scanned/image-only document.)'
            return jsonify({'type': 'text', 'filename': filename, 'content': text[:8000]})
        except Exception as e:
            print(f"[PDF read error] {repr(e)}")
            return jsonify({'error': 'Could not read that PDF file.'}), 400

    elif ext in ('png', 'jpg', 'jpeg', 'webp', 'gif'):
        try:
            data = file.read()
            b64 = base64.b64encode(data).decode('utf-8')
            mime = 'image/jpeg' if ext == 'jpg' else f'image/{ext}'
            data_url = f'data:{mime};base64,{b64}'
            return jsonify({'type': 'image', 'filename': filename, 'content': data_url})
        except Exception as e:
            print(f"[Image read error] {repr(e)}")
            return jsonify({'error': 'Could not read that image file.'}), 400

    else:
        return jsonify({'error': 'Unsupported file type. Please upload an image (PNG/JPG) or a PDF.'}), 400


@app.route('/search_messages', methods=['GET'])
@login_required
def search_messages():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT DISTINCT c.id, c.title, c.created_at FROM conversations c
        JOIN messages m ON m.conversation_id = c.id
        WHERE c.user_id = ? AND (m.content LIKE ? OR c.title LIKE ?)
        ORDER BY c.id DESC
    ''', (session['user_id'], f'%{q}%', f'%{q}%'))
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/get_response', methods=['POST'])
@login_required
def get_response():
    data = request.json or {}
    user_message = data.get('message', '').strip()
    conv_id = data.get('conversation_id')
    attachment = data.get('attachment')  # {'type': 'text'|'image', 'filename':..., 'content':...}

    if not user_message and not attachment:
        return jsonify({'error': 'Empty message'}), 400

    conn = get_db()
    c = conn.cursor()

    # What we display/store for the user's turn (keeps DB clean and small)
    display_message = user_message if user_message else '(sent an attachment)'
    if attachment:
        display_message += f"\n📎 {attachment.get('filename', 'file')}"

    # Create a conversation if one wasn't passed in
    if not conv_id:
        title = user_message[:40] + ('...' if len(user_message) > 40 else '') if user_message else (attachment.get('filename', 'New Chat') if attachment else 'New Chat')
        c.execute(
            'INSERT INTO conversations (user_id, title, created_at) VALUES (?, ?, ?)',
            (session['user_id'], title, datetime.now().isoformat())
        )
        conn.commit()
        conv_id = c.lastrowid
    else:
        c.execute('SELECT title FROM conversations WHERE id = ?', (conv_id,))
        row = c.fetchone()
        if row and row['title'] == 'New Chat':
            title = user_message[:40] + ('...' if len(user_message) > 40 else '') if user_message else (attachment.get('filename', 'New Chat') if attachment else 'New Chat')
            c.execute('UPDATE conversations SET title = ? WHERE id = ?', (title, conv_id))
            conn.commit()

    # Save user message (as displayed)
    c.execute(
        'INSERT INTO messages (conversation_id, sender, content, timestamp) VALUES (?, ?, ?, ?)',
        (conv_id, 'user', display_message, datetime.now().isoformat())
    )
    conn.commit()

    # Call the free Pollinations AI text endpoint
    url = "https://text.pollinations.ai/"

    system_prompt = (
        "You are a helpful, knowledgeable AI assistant, similar in style to ChatGPT. "
        "You can understand and respond fluently in ANY language the user writes in — "
        "Hindi, Hinglish, English, or any other language — always reply in the same "
        "language and script the user used. Handle any type of question well: factual, "
        "technical, coding, creative, personal advice, math, etc. Give clear, accurate, "
        "well-structured, and complete answers. Use short paragraphs, bullet points, "
        "numbered lists, or fenced code blocks (```language ... ```) when they genuinely "
        "improve readability. Be conversational and natural, not robotic. If the user "
        "shares a document or image, read it carefully and use its content to answer "
        "their question accurately. Ask a brief clarifying question only if the request "
        "is genuinely ambiguous. Keep responses focused and not unnecessarily long."
    )

    # Pull the last few turns of this conversation so the bot has context, like ChatGPT does
    c.execute(
        'SELECT sender, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 10',
        (conv_id,)
    )
    recent = list(reversed(c.fetchall()))

    history_messages = [{"role": "system", "content": system_prompt}]
    for m in recent[:-1]:  # everything except the message we just saved
        role = "user" if m['sender'] == 'user' else "assistant"
        history_messages.append({"role": role, "content": m['content']})

    # Build the current turn, attaching file content if present
    if attachment and attachment.get('type') == 'image':
        current_turn = {
            "role": "user",
            "content": [
                {"type": "text", "text": user_message or "Please describe/analyze this image."},
                {"type": "image_url", "image_url": {"url": attachment.get('content', '')}}
            ]
        }
    elif attachment and attachment.get('type') == 'text':
        combined_text = (
            f"[Attached file: {attachment.get('filename', 'document')}]\n"
            f"{attachment.get('content', '')}\n\n"
            f"User's question about this file: {user_message or 'Please summarize this document.'}"
        )
        current_turn = {"role": "user", "content": combined_text}
    else:
        current_turn = {"role": "user", "content": user_message}

    history_messages.append(current_turn)

    payload = {
        "messages": history_messages,
        "model": "openai",
        "jsonMode": False
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200 and response.text.strip():
            bot_reply = response.text.strip()
        else:
            print(f"[Pollinations API error] status={response.status_code} body={response.text[:300]}")
            bot_reply = "Main abhi is sawaal ka jawab nahi de paaya. Dobara koshish karein!"
    except Exception as e:
        print(f"[Pollinations API exception] {repr(e)}")
        bot_reply = "Lagta hai internet thoda thak gaya hai, ek baar aur koshish karein!"

    # Save bot reply
    c.execute(
        'INSERT INTO messages (conversation_id, sender, content, timestamp) VALUES (?, ?, ?, ?)',
        (conv_id, 'bot', bot_reply, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    return jsonify({'response': bot_reply, 'conversation_id': conv_id})


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)