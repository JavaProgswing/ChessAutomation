# ♟️ Chess Automation Client

This is a desktop automation tool that assists in making chess moves via a GUI interface. It interacts with a SpringBoot backend server and can provide suggestions, send moves, and integrate with Selenium-based automation.

---

## 📦 Requirements

Install dependencies via:

```bash
pip install -r requirements.txt
```

Make sure you have:

- Java JDK 17 or above
- Python 3.9 or above
- Admin privileges if running on Windows (for keyboard listening)

---

## 🚀 How to Start

Launch the app with:

```bash
java -jar server/chess-server-0.0.1.jar
python chess_client.py
```

This will:

- Spin up the springboot backend server for selenium automation.
- Launch the Tkinter GUI (`chess_client.py`) for interacting with the chess automation system

---

## 🕹️ Keyboard+UI Controls

- Interacting via the UI, board simulation
- `Alt + [a-h][1-8]`: Select squares (first = from, second = to)
- **Alt + &#96;**: Confirm the move

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

- GUI not showing? Check for errors in terminal
- API not responding? Confirm [http://127.0.0.1:8000/ping](http://127.0.0.1:8000/ping) works

---

## 📜 License

MIT — free to use, modify, and share.

---
