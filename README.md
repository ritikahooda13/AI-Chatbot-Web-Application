# AI Chat Assistant

A full-stack AI chatbot web application built with **Flask (Python)**, **SQLite**, and **Tailwind CSS**, created for Sqrock IT Solutions — Internship Project Phase 1, Task 1.

## Features

**Core requirements**
- Attractive, responsive homepage/UI
- Real-time chat interface (user message + AI response)
- Backend integration using Python (Flask)
- Typing/loading animation
- Chat history section (persisted in a database, not just the current session)

**Bonus features included**
- 🔐 Login / Signup system with hashed passwords (SQLite + Werkzeug)
- 📜 Persistent multi-conversation chat history (sidebar, like ChatGPT)
- 🌓 Dark / Light mode toggle
- 🎨 Multiple accent color themes (blue, violet, emerald, rose)
- 🎙️ Voice input (browser Speech Recognition API)
- 🔊 Text-to-speech — click the speaker icon on any bot reply to hear it read aloud
- 📎 File upload — attach an image or PDF and ask questions about it (vision + PDF text extraction)
- 💻 Code syntax highlighting for any code the AI returns
- 🔎 Search across all past chats from the sidebar
- 💾 Database integration (SQLite — users, conversations, messages)
- ⬇️ Download / export chat as `.txt` or `.pdf`
- 🗑️ Delete individual conversations
- 🌐 Strong multi-language support — replies in whatever language/script you write in
- 📱 Fully responsive (collapsible sidebar on mobile)

## Project Structure

```
ai-chatbot/
├── app.py                 # Flask backend (routes, auth, database, AI API call)
├── requirements.txt       # Python dependencies
├── chatbot.db              # SQLite database (auto-created on first run)
├── templates/
│   ├── index.html          # Main chat interface
│   ├── login.html          # Login page
│   └── register.html       # Sign-up page
└── static/                 # (reserved for any custom assets)
```

## How to Run

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the app**
   ```bash
   python app.py
   ```

3. **Open in browser**
   ```
   http://127.0.0.1:5001
   ```

4. Sign up for a new account, then start chatting!

## How It Works

- The frontend sends the user's message to `/get_response` via `fetch()`.
- The Flask backend forwards the message to the free **Pollinations AI** text API and gets a reply.
- Every message (user + bot) is saved to the `messages` table, linked to a `conversations` row, which is linked to the logged-in `user`.
- The sidebar loads all of a user's past conversations from `/conversations`, and clicking one loads its full message history from `/conversation/<id>`.

