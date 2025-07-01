# ♟️ Chess Automation Client

This is a desktop automation tool that assists in making chess moves via a GUI interface. It interacts with a FastAPI backend server and can provide suggestions, send moves, and integrate with Selenium-based automation.

---

## 📦 Requirements

Install dependencies via:

```bash
pip install -r requirements.txt
```

Make sure you have:

- Python 3.9 or above
- Chrome browser
- Admin privileges if running on Windows (for keyboard listening)

---

## 🚀 How to Start

Launch the app with:

```bash
python main.py
```

This will:

- Start the FastAPI server (`server.py`)
- Launch the Tkinter GUI (`chess_client.py`) for interacting with the chess automation system

---

## 🕹️ Keyboard Controls

- `Alt + [a-h][1-8]`: Select squares (first = from, second = to)
- `Alt + \``: Confirm the move
- `Alt + 1`: Undo last square
- `Alt + 2`: Cancel the move
- `Alt + 3`: Open bot selector
- `Alt + p`: Promote piece (`q`, `r`, `b`, `n`)

---

## 🎛️ Features

- Move input via keyboard overlay
- GUI that stays on top of other windows
- WebSocket communication with backend
- Built-in bot switching
- Promotion control
- Auto-restarts if you cancel window close
- Integrates with Selenium via `chess.py`

---

## 🔧 File Structure

```
.
├── main.py           # Entry point
├── server.py         # FastAPI backend
├── chess_client.py   # Tkinter GUI client
├── chess.py          # Automation logic using Selenium
├── requirements.txt  # Dependencies
└── README.md         # This file
```

---

## 💡 Tip

If `keyboard` module doesn’t capture keys:

- Run with admin privileges
- Ensure your layout is US/QWERTY or adjust mapping logic

---

## ❓ Troubleshooting

- GUI not showing? Check for errors in terminal
- API not responding? Confirm [http://127.0.0.1:8000/ping](http://127.0.0.1:8000/ping) works
- Selenium issues? Ensure `chromedriver` is in your PATH

---

## 📜 License

MIT — free to use, modify, and share.

---
