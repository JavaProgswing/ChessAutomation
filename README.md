# ♟️ Chess Automation Client

This is a desktop automation tool that assists in making chess moves via a GUI interface. It interacts with a remote backend server and can provide suggestions, send moves, and integrate with Selenium-based automation.

---

## 📦 Requirements

Install dependencies via:

```bash
pip install -r requirements.txt
```

Make sure you have:

- Python 3.9 or above
- Admin privileges if running on Windows (for keyboard listening)

---

## 🚀 How to Start

1. **Start the Backend Server**:
   ```bash
   java -jar server/chess-server-0.0.1.jar
   ```

2. **Start the Client**:

   **Option A: Run from Source**
   ```bash
   python chess_client.py
   ```

   **Option B: Run Executable**
   - Build: `python build_exe.py`
   - Run: `dist/ChessAutomation.exe`

This will launch the Tkinter GUI. The client connects to the local server at `http://127.0.0.1:8000`.

---

## 🕹️ Keyboard+UI Controls

- Interacting via the UI, board simulation
- `Alt + [a-h][1-8]`: Select squares (first = from, second = to)
- **Alt + `**: Confirm the move

## 🎛️ Features

- Move input via keyboard overlay/UI
- Built-in bot switching
- Promotion control
- Chess game analysis via chess.com

---

## 💡 Tip

If `keyboard` module doesn’t capture keys:

- Run with admin privileges
- Ensure your layout is US/QWERTY or adjust mapping logic

---

## ❓ Troubleshooting

- GUI not showing? Check for errors in terminal (if running from source)
- API not responding? Ensure you have internet connection to reach the remote server.

---

## 📜 License

MIT — free to use, modify, and share.

---
