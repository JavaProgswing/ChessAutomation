import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import threading
import asyncio
import websockets
import requests
import keyboard
import time
import json
import traceback
import chess
import io
from chess import pgn

API_URL = "http://127.0.0.1:8000"
WS_URL = f"{API_URL.replace('http', 'ws')}/ws"

PIECES = {
    "wK": "♔",
    "wQ": "♕",
    "wR": "♖",
    "wB": "♗",
    "wN": "♘",
    "wP": "♙",
    "bK": "♚",
    "bQ": "♛",
    "bR": "♜",
    "bB": "♝",
    "bN": "♞",
    "bP": "♟",
}


def log_exception(e):
    with open("error.log", "a") as f:
        f.write(f"{time.ctime()}\n")
        f.write(traceback.format_exc())
        f.write("\n\n")


def log_info(message):
    with open("info.log", "a", encoding="utf-8") as f:
        f.write(f"{time.ctime()}\n")
        f.write(message)
        f.write("\n\n")


# -------------------- ChessBoard --------------------
class ChessBoard(tk.Frame):
    def __init__(self, parent, client, square_size=48):
        super().__init__(parent, bg="black")
        self.client = client
        self.rows = 8
        self.cols = 8
        self.tiles = {}
        self.selected = None
        self.suggested_move = None  # new
        self.square_size = square_size
        self.create_board()

    def create_board(self):
        for r in range(self.rows):
            for c in range(self.cols):
                color = "#eeeed2" if (r + c) % 2 == 0 else "#769656"
                lbl = tk.Label(
                    self,
                    text="",
                    bg=color,
                    font=("Courier", 20),
                    width=2,
                    height=1,
                    relief="flat",
                    borderwidth=1,
                )
                lbl.grid(row=r, column=c, padx=0, pady=0, ipadx=2, ipady=2)
                lbl.bind("<Button-1>", lambda e, row=r, col=c: self.on_click(row, col))
                lbl.bind(
                    "<Double-Button-1>",
                    lambda e, row=r, col=c: self.on_double_click(row, col),
                )
                self.tiles[(r, c)] = lbl

    def highlight_square(self, row, col, color):
        lbl = self.tiles[(row, col)]
        original_color = "#eeeed2" if (row + col) % 2 == 0 else "#769656"
        lbl.config(bg=color)
        self.after(900, lambda: lbl.config(bg=original_color))

    def update_board(self, board_state, suggested_move=None):
        self.suggested_move = suggested_move
        for r in range(self.rows):
            for c in range(self.cols):
                sq = f"{chr(ord('a') + c)}{8 - r}"
                piece_code = board_state.get(sq, "")
                lbl = self.tiles[(r, c)]
                piece = PIECES.get(piece_code, "")
                lbl.config(text=piece)
                # highlight suggested move
                if suggested_move and sq in suggested_move:
                    lbl.config(bg="#f7ec6f")
                else:
                    lbl.config(bg="#eeeed2" if (r + c) % 2 == 0 else "#769656")

    def on_click(self, row, col):
        if not self.client.listening or not self.client.game_active:
            return
        square = f"{chr(ord('a') + col)}{8 - row}"
        if not self.selected:
            self.selected = (row, col)
            self.client.from_sq = square
            self.highlight_square(row, col, "#6cf")
            self.client.update_status(
                f"[From] {self.client.from_sq}\nSelect destination"
            )
        else:
            self.client.to_sq = square
            self.highlight_square(row, col, "#6cf")
            self.client.update_status(
                f"[To] {self.client.to_sq} Confirm Move or Press Alt + `"
            )
            self.selected = None

    def on_double_click(self, row, col):
        # optional: same as click
        self.on_click(row, col)


# -------------------- Chess Client --------------------
class ChessClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Chess Client")
        self.root.attributes("-alpha", 0.95)
        self.root.attributes("-topmost", True)
        self.root.geometry("+10+10")
        self.root.overrideredirect(True)
        self.root.configure(bg="black")

        # Window drag
        self.offset_x = 0
        self.offset_y = 0
        self.root.bind("<Button-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)

        # Main frame
        self.main_frame = tk.Frame(root, bg="black", padx=8, pady=4)
        self.main_frame.pack(side="left")

        # Close button
        self.close_button = tk.Button(
            self.main_frame,
            text="×",
            command=self.on_close,
            bg="black",
            fg="red",
            borderwidth=0,
        )
        self.close_button.pack(anchor="ne", pady=(0, 4))

        # Status
        self.status = tk.StringVar()
        self.update_status("Welcome! Login or Continue as guest.")
        self.pgn = None
        self.move_no = 0

        # Login / Continue buttons
        self.login_btn = tk.Button(
            self.main_frame,
            text="Login",
            command=self.login_flow,
            bg="#444",
            fg="white",
        )
        self.login_btn.pack(pady=4)
        self.continue_btn = tk.Button(
            self.main_frame,
            text="Continue",
            command=self.show_side_select,
            bg="#444",
            fg="white",
        )
        self.continue_btn.pack(pady=4)

        # Toggle board button (hidden until game started)
        self.toggle_board_btn = tk.Button(
            self.main_frame,
            text="Show Board",
            command=self.toggle_board,
            bg="#444",
            fg="white",
        )
        self.toggle_board_btn.pack(pady=4)
        self.toggle_board_btn.pack_forget()

        # Chess board
        self.board_frame = ChessBoard(self.main_frame, self)
        self.board_frame.pack(pady=(8, 0))
        self.board_frame.pack_forget()

        # Status label
        self.status_label = tk.Label(
            self.main_frame,
            textvariable=self.status,
            fg="lime",
            bg="black",
            font=("Courier", 11, "bold"),
            wraplength=300,
            justify="left",
        )
        self.status_label.pack(anchor="w", fill="x", pady=(6, 0))

        # Current bot display
        self.current_bot_frame = tk.Frame(self.main_frame, bg="black")
        self.current_bot_avatar = tk.Label(self.current_bot_frame, bg="black")
        self.current_bot_avatar.pack(side="left", padx=(0, 6))
        self.current_bot_label = tk.Label(
            self.current_bot_frame,
            text="",
            fg="lime",
            bg="black",
            font=("Courier", 11, "bold"),
        )
        self.current_bot_label.pack(side="left")
        self.current_bot_frame.pack(anchor="w", pady=(4, 0))
        self.current_bot_frame.pack_forget()

        # Action buttons frame
        self.action_frame = tk.Frame(self.main_frame, bg="black")

        # Top row: Confirm, Undo, Cancel
        top_actions = tk.Frame(self.action_frame, bg="black")
        self.confirm_btn = tk.Button(
            top_actions,
            text="Confirm Move",
            command=self.confirm_move,
            bg="#2d7",
            fg="black",
        )
        self.undo_btn = tk.Button(
            top_actions,
            text="Undo",
            command=lambda: asyncio.run(self.send_undo()),
            bg="#444",
            fg="white",
        )
        self.cancel_btn = tk.Button(
            top_actions,
            text="Cancel",
            command=self.clear_buffer,
            bg="#444",
            fg="white",
        )
        self.confirm_btn.pack(side="left", padx=4)
        self.undo_btn.pack(side="left", padx=4)
        self.cancel_btn.pack(side="left", padx=4)
        top_actions.pack(anchor="w", pady=(0, 4))

        # Bottom row: Promote, Select Bot
        bottom_actions = tk.Frame(self.action_frame, bg="black")
        self.promote_btn = tk.Button(
            bottom_actions,
            text="Promote",
            command=lambda: asyncio.run(self.send_promotion()),
            bg="#444",
            fg="white",
        )
        self.bot_btn = tk.Button(
            bottom_actions,
            text="Select Bot",
            command=self.show_bot_selector,
            bg="#444",
            fg="white",
        )
        self.promote_btn.pack(side="left", padx=4)
        self.bot_btn.pack(side="left", padx=4)
        bottom_actions.pack(anchor="w", pady=(0, 4))

        # Hide action frame initially
        self.action_frame.pack_forget()

        # Game / WS state
        self.game_active = False
        self.listening = True
        self.ws = None
        self.from_sq = ""
        self.to_sq = ""
        self.key_buffer = []
        self.move_timer = None
        self.processing = False
        self.bots = []

    # -------------------- Clear buffer --------------------
    def clear_buffer(self):
        self.from_sq = ""
        self.to_sq = ""
        self.key_buffer.clear()
        self.update_status("[Clear] Cleared From Square")

    # -------------------- Bot selector --------------------
    def show_bot_selector(self):
        if not self.bots:
            self.update_status("No bots available")
            return

        selector = tk.Toplevel(self.root)
        selector.title("Select Bot")
        selector.configure(bg="black")

        tk.Label(
            selector,
            text="Select a bot:",
            fg="lime",
            bg="black",
            font=("Courier", 12, "bold"),
        ).pack(pady=(6, 4))

        bot_var = tk.StringVar(value="")
        level_scale = None

        def select_bot_action():
            sel_name = bot_var.get()
            if not sel_name:
                selector.destroy()
                return
            selected_bot = next((b for b in self.bots if b["name"] == sel_name), None)
            if not selected_bot:
                selector.destroy()
                return
            payload = {"action": "select_bot", "bot_id": selected_bot["id"]}
            if selected_bot.get("is_engine") and level_scale:
                payload["engine_level"] = level_scale.get()
            asyncio.run(self.ws.send(payload))
            selector.destroy()

        for bot in self.bots:
            b_frame = tk.Frame(selector, bg="black")
            try:
                from PIL import Image, ImageTk
                import requests
                from io import BytesIO

                resp = requests.get(bot["avatar"])
                img = Image.open(BytesIO(resp.content)).resize((32, 32))
                bot_img = ImageTk.PhotoImage(img)
                bot_label = tk.Label(b_frame, image=bot_img, bg="black")
                bot_label.image = bot_img
                bot_label.pack(side="left", padx=(0, 4))
            except Exception:
                pass
            tk.Radiobutton(
                b_frame,
                text=f"{bot['name']} [{bot['rating']}]",
                variable=bot_var,
                value=bot["name"],
                fg="lime",
                bg="black",
                selectcolor="#222",
            ).pack(side="left")
            b_frame.pack(anchor="w", pady=2)

        # Engine level scale (for engines)
        level_scale = tk.Scale(
            selector, from_=1, to=25, orient="horizontal", bg="black", fg="white"
        )
        level_scale.pack(fill="x", padx=6, pady=(4, 6))

        tk.Button(
            selector, text="Select", command=select_bot_action, bg="#2d7", fg="black"
        ).pack(pady=(0, 6))

    # -------------------- Window Drag --------------------
    def start_move(self, event):
        self.offset_x = event.x
        self.offset_y = event.y

    def do_move(self, event):
        x = event.x_root - self.offset_x
        y = event.y_root - self.offset_y
        self.root.geometry(f"+{x}+{y}")

    # -------------------- Status --------------------
    def update_status(self, msg):
        self.root.after(0, lambda: self.status.set(msg))
        log_info(msg)

    # -------------------- Login Flow --------------------
    def login_flow(self):
        username = simpledialog.askstring(
            "Login", "Chess.com Username", parent=self.root
        )
        if not username:
            return
        try:
            profile_req = requests.get(f"{API_URL}/api/chess/profile/{username}")
            profile = profile_req.json()
            if profile_req.status_code != 200:
                raise Exception(profile.get("error", "Unknown error"))
            games_req = requests.get(f"{API_URL}/api/chess/games/{username}")
            games = games_req.json()
            if games_req.status_code != 200:
                raise Exception(games.get("error", "Unknown error"))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch profile/games: {e}")
            return

        # Compute display_result and move counts for each game and attach profile
        for g in games:
            w_name = g["white"]["username"]
            b_name = g["black"]["username"]
            w_res = g["white"].get("result", "")
            b_res = g["black"].get("result", "")
            if w_res.lower() == "agreed" or b_res.lower() == "agreed":
                g["display_result"] = "Draw"
            elif w_res != b_res:
                g["display_result"] = w_name if w_res == "win" else b_name
                g["display_result"] = f"{g['display_result']} won"
            else:
                g["display_result"] = w_res.capitalize()

            # Determine half-move count from PGN (safe)
            try:
                pgn_io = io.StringIO(g.get("pgn", ""))
                game_pgn = pgn.read_game(pgn_io)
                g_moves = list(game_pgn.mainline_moves()) if game_pgn else []
                g["halfmove_count"] = len(g_moves)
            except Exception:
                g["halfmove_count"] = max(0, len(g.get("pgn", "").split()))

        # hide login/continue buttons now that user is logged in
        self.login_btn.pack_forget()
        self.continue_btn.pack_forget()

        # show games (include profile info in the same window)
        self.show_games(profile, games)

    # -------------------- Game Selection / Viewer --------------------
    def show_games(self, profile, games):
        top = tk.Toplevel(self.root)
        top.title("Select Game")
        top.geometry("750x520")
        top.configure(bg="black")

        # Left: profile + controls, Right: games tree
        left = tk.Frame(top, bg="black", padx=8, pady=8)
        left.pack(side="left", fill="y")
        right = tk.Frame(top, bg="black", padx=8, pady=8)
        right.pack(side="right", expand=True, fill="both")

        # Profile info
        tk.Label(
            left,
            text=f"{profile.get('username')}",
            fg="white",
            bg="black",
            font=("Courier", 14, "bold"),
        ).pack(anchor="w")
        tk.Label(
            left, text=f"Status: {profile.get('status','-')}", fg="lime", bg="black"
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            left,
            text=f"Followers: {profile.get('followers','-')}",
            fg="white",
            bg="black",
        ).pack(anchor="w")
        if profile.get("country"):
            headers = {"User-Agent": "ChessAutomation/1.0"}
            try:
                country_data = requests.get(
                    profile.get("country"), headers=headers
                ).json()
                tk.Label(
                    left,
                    text=f"Country: {country_data.get('name', profile.get('country'))}",
                    fg="white",
                    bg="black",
                    wraplength=200,
                ).pack(anchor="w")
            except Exception:
                pass
        tk.Label(left, text=" ", bg="black").pack()  # spacer

        # Move spinbox
        tk.Label(
            left, text="Move to start from (cannot pick 1):", fg="lime", bg="black"
        ).pack(anchor="w", pady=(8, 0))
        move_spin_var = tk.StringVar(value="2")
        move_spin = tk.Spinbox(left, textvariable=move_spin_var, from_=2, to=2, width=6)
        move_spin.pack(anchor="w", pady=(2, 6))

        # Buttons
        start_btn = tk.Button(
            left, text="Start from Selected Move", bg="#2d7", fg="black"
        )
        start_btn.pack(fill="x", pady=(6, 4))
        view_btn = tk.Button(left, text="Open Game Viewer", bg="#444", fg="white")
        view_btn.pack(fill="x", pady=(0, 6))
        close_btn = tk.Button(
            left, text="Close", bg="#333", fg="white", command=top.destroy
        )
        close_btn.pack(side="bottom", fill="x", pady=(8, 0))

        # Tree on right for games (balanced columns)
        tree = ttk.Treeview(
            right, columns=("game", "result"), show="headings", height=15
        )
        tree.heading("game", text="Game")
        tree.heading("result", text="Result")

        # Equal space distribution (relative width)
        tree.column("game", anchor="center", width=350, stretch=True)
        tree.column("result", anchor="center", width=350, stretch=True)

        tree.pack(expand=True, fill="both")

        # Make sure columns resize equally when window expands
        tree.bind(
            "<Configure>",
            lambda e: [
                tree.column("game", width=int(e.width / 2)),
                tree.column("result", width=int(e.width / 2)),
            ],
        )
        uuid_to_game = {}

        for g in games:
            safe_id = g.get("uuid") or str(time.time())  # fallback to timestamp
            uuid_to_game[safe_id] = g

            white = g.get("white", {}).get("username", "Unknown")
            black = g.get("black", {}).get("username", "Unknown")
            result = g.get("display_result", "")
            halfmoves = g.get("halfmove_count", 0)
            game_label = f"{white} vs {black} ({halfmoves or 'N/A'} moves)"

            tree.insert("", "end", iid=safe_id, values=(game_label, result))

        # Handle selection change
        def on_select(event=None):
            sel = tree.focus()
            if not sel:
                return
            g = uuid_to_game.get(sel)
            hm = g.get("halfmove_count", 0)
            min_allowed = 2
            max_allowed = max(2, hm - 2)
            try:
                move_spin.config(from_=min_allowed, to=max_allowed)
                cur = (
                    int(move_spin_var.get())
                    if move_spin_var.get().isdigit()
                    else min_allowed
                )
                if cur < min_allowed:
                    move_spin_var.set(str(min_allowed))
                elif cur > max_allowed:
                    move_spin_var.set(str(max_allowed))
            except Exception:
                move_spin_var.set(str(min_allowed))

        tree.bind("<<TreeviewSelect>>", on_select)

        # View game
        def open_viewer():
            sel = tree.focus()
            if not sel:
                messagebox.showerror("Error", "Select a game first")
                return
            g = uuid_to_game.get(sel)
            if not g:
                messagebox.showerror("Error", "Game not found")
                return
            self.show_game_viewer(g)

        view_btn.config(command=open_viewer)

        # Start game from selected move
        def start_from_selected():
            sel = tree.focus()
            if not sel:
                messagebox.showerror("Error", "Select a game first")
                return
            g = uuid_to_game.get(sel)
            if not g:
                messagebox.showerror("Error", "Game not found")
                return

            try:
                chosen = int(move_spin_var.get())
            except Exception:
                messagebox.showerror("Error", "Invalid move number")
                return

            hm = g.get("halfmove_count", 0)
            min_allowed = 2
            max_allowed = max(2, hm - 2)
            if chosen < min_allowed or chosen > max_allowed:
                messagebox.showerror(
                    "Error", f"Choose between {min_allowed} and {max_allowed}"
                )
                return

            self.pgn = g.get("pgn")
            self.move_no = chosen - 2
            top.destroy()
            self.start_ws()
            self.toggle_board_btn.pack(pady=4)

        start_btn.config(command=start_from_selected)

        # Preselect first item
        first = tree.get_children()
        if first:
            tree.selection_set(first[0])
            tree.focus(first[0])
            on_select()

    def show_game_viewer(self, game):
        # Viewer window that allows stepping through PGN (board displayed)
        viewer = tk.Toplevel(self.root)
        viewer.title("Game Viewer")
        viewer.configure(bg="black")

        info = tk.Label(
            viewer,
            text=f"{game['white']['username']} vs {game['black']['username']}  -  {game.get('display_result','')}",
            fg="white",
            bg="black",
            font=("Courier", 12, "bold"),
        )
        info.pack(pady=(6, 0))

        board_frame = ChessBoard(viewer, self)
        board_frame.pack(pady=(6, 6))

        pgn_text = game.get("pgn", "")
        try:
            pgn_io = io.StringIO(pgn_text)
            game_pgn = pgn.read_game(pgn_io)
            board = game_pgn.board() if game_pgn else chess.Board()
            moves = list(game_pgn.mainline_moves()) if game_pgn else []
        except Exception:
            board = chess.Board()
            moves = []
        move_index = 0

        def board_state_from_board(bd):
            state = {}
            for sq in chess.SQUARES:
                p = bd.piece_at(sq)
                if p:
                    color = "w" if p.color else "b"
                    state[chess.SQUARE_NAMES[sq]] = f"{color}{p.symbol().upper()}"
            return state

        def update_board():
            bs = board_state_from_board(board)
            board_frame.update_board(bs)
            info.config(
                text=f"{game['white']['username']} vs {game['black']['username']}  -  {game.get('display_result','')}    [{move_index}/{len(moves)}]"
            )

        def next_move():
            nonlocal move_index
            if move_index < len(moves):
                board.push(moves[move_index])
                move_index += 1
                update_board()

        def prev_move():
            nonlocal move_index
            if move_index > 0:
                board.pop()
                move_index -= 1
                update_board()

        ctrl = tk.Frame(viewer, bg="black")
        tk.Button(ctrl, text="Previous", command=prev_move, bg="#444", fg="white").pack(
            side="left", padx=6
        )
        tk.Button(ctrl, text="Next", command=next_move, bg="#2d7", fg="black").pack(
            side="left", padx=6
        )
        ctrl.pack(pady=(0, 8))

        update_board()

    # -------------------- Continue Guest --------------------
    def show_side_select(self):
        # Create a small popup window for side selection
        side_window = tk.Toplevel(self.root)
        side_window.title("Choose Your Side")
        side_window.configure(bg="#121212")
        side_window.geometry("250x150")
        side_window.resizable(False, False)

        tk.Label(
            side_window,
            text="Select your side:",
            bg="#121212",
            fg="lime",
            font=("Courier", 11, "bold"),
        ).pack(pady=10)

        button_frame = tk.Frame(side_window, bg="#121212")
        button_frame.pack(pady=10)

        def choose(side):
            self.side = side
            side_window.destroy()

            # Hide login/continue because user moved on
            self.login_btn.pack_forget()
            self.continue_btn.pack_forget()

            # Start WebSocket connection
            self.start_ws()

            # Show toggle board button for guest runs
            self.toggle_board_btn.pack(pady=4)

        white_btn = tk.Button(
            button_frame,
            text="♔  White",
            bg="#f0f0f0",
            fg="black",
            relief="ridge",
            font=("Segoe UI", 10, "bold"),
            width=10,
            command=lambda: choose("white"),
        )
        black_btn = tk.Button(
            button_frame,
            text="♚  Black",
            bg="#1e1e1e",
            fg="white",
            relief="ridge",
            font=("Segoe UI", 10, "bold"),
            width=10,
            command=lambda: choose("black"),
        )

        white_btn.pack(side="left", padx=10)
        black_btn.pack(side="right", padx=10)

        # Optional: subtle fade-in animation for style
        try:
            side_window.attributes("-alpha", 0.0)
            for i in range(1, 11):
                side_window.attributes("-alpha", i / 10)
                side_window.update()
                side_window.after(20)
        except Exception:
            pass

    # -------------------- Toggle Board --------------------
    def toggle_board(self):
        if not self.game_active:
            # if no game started, show a message
            messagebox.showinfo("Not active", "Start a game first.")
            return
        if self.board_frame.winfo_ismapped():
            self.board_frame.pack_forget()
            self.toggle_board_btn.config(text="Show Board")
        else:
            self.board_frame.pack(pady=(8, 0))
            self.toggle_board_btn.config(text="Hide Board")

    # -------------------- WebSocket --------------------
    def start_ws(self):
        # Show action buttons but keep board hidden by default
        self.action_frame.pack(pady=(8, 6))
        self.game_active = True

        self.key_listener_thread = threading.Thread(
            target=self.key_listener, daemon=True
        )
        self.key_listener_thread.start()
        self.ws_thread = threading.Thread(
            target=lambda: asyncio.run(self.websocket_loop()), daemon=True
        )
        self.ws_thread.start()

    def update_bot_display(self, bot):
        self.current_bot_label.config(text=f"{bot['name']} [{bot.get('rating','N/A')}]")
        avatar_url = bot.get("avatar")
        if avatar_url:
            try:
                from PIL import Image, ImageTk
                import requests
                from io import BytesIO

                resp = requests.get(avatar_url)
                img = Image.open(BytesIO(resp.content)).resize((32, 32))
                self.current_bot_avatar.imgtk = ImageTk.PhotoImage(img)
                self.current_bot_avatar.config(image=self.current_bot_avatar.imgtk)
            except Exception:
                self.current_bot_avatar.config(image="")
        self.current_bot_frame.pack(anchor="w", pady=(4, 0))

    async def websocket_loop(self):
        try:
            async with websockets.connect(WS_URL) as websocket:
                self.ws = websocket
                init_payload = {"action": "init"}
                if self.pgn:
                    init_payload["pgn"] = self.pgn
                    init_payload["move_no"] = self.move_no
                else:
                    init_payload["side"] = self.side
                await websocket.send(json.dumps(init_payload))
                current_time = time.time()
                waiting_for_init = True

                def update_status_with_time():
                    nonlocal waiting_for_init
                    while not waiting_for_init:
                        elapsed = time.time() - current_time
                        self.update_status(
                            f"Connected to server. Waiting for game to start... ({elapsed}s)"
                        )
                        time.sleep(0.1)

                self.update_status("Connected to server. Waiting for game to start...")
                threading.Thread(target=update_status_with_time, daemon=True).start()
                while True:
                    msg = await websocket.recv()
                    try:
                        data = json.loads(msg)
                    except Exception:
                        data = {"raw": msg}
                    print(data)

                    msg_type = data.get("type")
                    state = data.get("state")
                    if msg_type == "init" and data.get("current_bot"):
                        bot = data["current_bot"]
                        self.bots = data.get("bots", [])
                        print("Available bots:", self.bots)
                        self.update_bot_display(bot)

                        board_state = state
                        self.board_frame.update_board(
                            board_state, f"{data.get('from')}{data.get('to')}"
                        )
                        waiting_for_init = False

                    if msg_type == "engine_move" and state:
                        board_state = state
                        self.board_frame.update_board(
                            board_state, f"{data.get('from')}{data.get('to')}"
                        )

                    status_msg = data.get("status") or data.get("error") or str(data)
                    self.update_status(f"WS ▶ {status_msg}")
        except Exception as e:
            log_exception(e)
            self.update_status(f"WebSocket error: {e}")
            if isinstance(e, websockets.exceptions.ConnectionClosedError):
                messagebox.showerror(
                    "Server Connection Closed", "Shutting down client, please restart."
                )
                self.on_close()

    def clear_buffer_timeout(self):
        self.clear_buffer()
        self.update_status("[Timeout] Cleared From Square")

    # -------------------- Move / Undo / Promote --------------------
    def confirm_move(self):
        if not self.from_sq or not self.to_sq or not self.game_active:
            self.update_status("[ERROR] Invalid move")
            return
        asyncio.run(self.send_move(self.from_sq, self.to_sq))
        self.from_sq = ""
        self.to_sq = ""

    async def send_move(self, f, t):
        if not self.ws:
            return
        payload = {"action": "next_move", "opponent_move": f"{f}{t}"}
        await self.ws.send(json.dumps(payload))

    async def send_undo(self):
        if not self.ws or not self.game_active:
            return
        await self.ws.send(json.dumps({"action": "undo"}))

    async def send_promotion(self):
        if not self.ws or not self.game_active:
            return
        piece = simpledialog.askstring(
            "Promotion", "Enter piece (Q/R/B/N)", parent=self.root
        )
        if piece and piece.upper() in ["Q", "R", "B", "N"]:
            await self.ws.send(
                json.dumps({"action": "promote", "piece": piece.lower()})
            )
        else:
            self.update_status("[ERROR] Invalid piece for promotion")

    async def send_bot(self, bot_name):
        if not self.ws:
            return
        await self.ws.send(json.dumps({"action": "select_bot", "bot": bot_name}))

    # -------------------- Key Listener --------------------
    def key_listener(self):
        while True:
            if not self.listening or not self.game_active:
                time.sleep(0.1)
                continue

            # Alt+` confirm
            if keyboard.is_pressed("alt+`") and self.from_sq and self.to_sq:
                self.processing = True
                self.update_status(f"[Processing] {self.from_sq}{self.to_sq}")
                asyncio.run(self.send_move(self.from_sq, self.to_sq))
                self.clear_buffer()
                time.sleep(0.25)
                continue

            # Capture square input (Alt held)
            if keyboard.is_pressed("alt"):
                for key in "abcdefgh12345678":
                    if keyboard.is_pressed(key):
                        if key not in self.key_buffer:
                            self.key_buffer.append(key)
                            if len(self.key_buffer) == 2:
                                sq = "".join(self.key_buffer[:2])
                                if not self.from_sq:
                                    self.from_sq = sq
                                    self.update_status(
                                        f"[From] {self.from_sq}\nWaiting for destination...\nAlt+`=confirm, Alt+2=cancel, Alt+9=undo"
                                    )
                                elif not self.to_sq:
                                    self.to_sq = sq
                                    self.update_status(
                                        f"[To] {self.to_sq}\nAlt+`=confirm, Alt+2=cancel, Alt+9=undo"
                                    )
                                self.key_buffer.clear()
                                if self.move_timer:
                                    self.move_timer.cancel()
                                self.move_timer = threading.Timer(
                                    5, self.clear_buffer_timeout
                                )
                                self.move_timer.start()
            time.sleep(0.05)

    def cancel_move(self):
        if not self.game_active:
            return
        self.from_sq = ""
        self.to_sq = ""
        self.update_status("Move cancelled.")

    # -------------------- Close --------------------
    def on_close(self):
        self.listening = False
        try:
            self.root.destroy()
        except Exception:
            pass


# -------------------- Run --------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = ChessClient(root)
    root.mainloop()
