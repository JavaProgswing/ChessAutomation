import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import threading
import asyncio
import websockets
import requests
import keyboard
import time
import json
import os

API_URL = "http://127.0.0.1:8000"
WS_URL = f"{API_URL.replace('http', 'ws')}/ws"


class ChessClient:
    def __init__(self, root):
        self.root = root
        self.root.attributes("-alpha", 0.95)
        self.root.attributes("-topmost", True)
        self.root.geometry("+10+10")
        self.root.overrideredirect(True)
        self.root.configure(bg="black")

        self.offset_x = 0
        self.offset_y = 0
        self.root.bind("<Button-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)

        self.main_frame = tk.Frame(root, bg="black", padx=8, pady=4)
        self.main_frame.pack()

        self.close_button = tk.Button(
            self.main_frame,
            text="×",
            command=self.on_close,
            bg="black",
            fg="red",
            borderwidth=0,
            font=("Courier", 12, "bold"),
            activebackground="black",
            activeforeground="red",
            padx=4,
        )
        self.close_button.pack(anchor="ne", pady=(0, 4))

        self.status = tk.StringVar()
        self.update_status(
            "\nChess Automation Client\n"
            "Press Alt + a-h1-8 (from)\n"
            "then Alt + a-h1-8 (to)\n"
            "Alt + ` = confirm\n"
            "Alt + 9 = undo move\n"
            "Alt + 2 = cancel\n"
            "Alt + 3 = change bot\n"
            "Alt + p = promote\n"
            "\nSelect your side and click Start to begin."
        )
        self.status.trace_add("write", self.update_window_size)

        self.side = tk.StringVar(value="white")
        self.first_move = True

        self.controls_frame = tk.Frame(self.main_frame, bg="black")
        self.white_rb = tk.Radiobutton(
            self.controls_frame,
            text="White",
            variable=self.side,
            value="white",
            bg="black",
            fg="white",
            selectcolor="black",
            activebackground="black",
            activeforeground="white",
            highlightthickness=0,
            borderwidth=0,
        )
        self.black_rb = tk.Radiobutton(
            self.controls_frame,
            text="Black",
            variable=self.side,
            value="black",
            bg="black",
            fg="white",
            selectcolor="black",
            activebackground="black",
            activeforeground="white",
            highlightthickness=0,
            borderwidth=0,
        )
        self.start_btn = tk.Button(
            self.controls_frame,
            text="Start",
            command=self.start_client,
            bg="#444",
            fg="white",
            activebackground="#666",
            activeforeground="white",
            relief="flat",
            padx=6,
            pady=2,
        )

        self.white_rb.pack(side="left", padx=4)
        self.black_rb.pack(side="left", padx=4)
        self.start_btn.pack(side="left", padx=4)
        self.controls_frame.pack(pady=(0, 4))

        self.status_label = tk.Label(
            self.main_frame,
            textvariable=self.status,
            fg="lime",
            bg="black",
            font=("Courier", 11, "bold"),
            wraplength=300,
            justify="left",
        )
        self.status_label.pack(anchor="w", fill="x")

        self.from_sq = ""
        self.to_sq = ""
        self.move_timer = None
        self.ws = None
        self.bots = []
        self.listening = True

    def start_move(self, event):
        self.offset_x = event.x
        self.offset_y = event.y

    def do_move(self, event):
        x = event.x_root - self.offset_x
        y = event.y_root - self.offset_y
        self.root.geometry(f"+{x}+{y}")

    def update_window_size(self, *_):
        self.root.update_idletasks()
        width = self.status_label.winfo_reqwidth() + 30
        height = self.main_frame.winfo_reqheight() + 10
        self.root.geometry(f"{width}x{height}")

    def start_client(self):
        if not self.check_api():
            messagebox.showerror("API Error", "Server not available at /ping")
            return

        self.update_status("Initializing...")
        self.controls_frame.pack_forget()
        threading.Thread(target=self.run_key_listener, daemon=True).start()
        threading.Thread(target=self.run_websocket_loop, daemon=True).start()

    def check_api(self):
        try:
            r = requests.get(f"{API_URL}/ping")
            return r.status_code == 200 and r.json().get("status") == "Ok"
        except:
            return False

    def clear_buffer(self):
        self.from_sq = ""
        self.to_sq = ""
        self.update_status("...")

    def clear_buffer_timeout(self):
        self.from_sq = ""
        self.to_sq = ""

    def run_key_listener(self):
        self.processing = False
        while True:
            if keyboard.is_pressed("alt"):
                keys = []
                start_time = time.time()
                while time.time() - start_time < 10:
                    if keyboard.is_pressed("alt+3") and (
                        not any([keyboard.is_pressed(key) for key in "abcdefgh"])
                    ):
                        self.listening = not self.listening
                        if not self.listening:
                            self.show_bot_selector()
                        time.sleep(0.5)
                        continue

                    if not self.listening:
                        time.sleep(0.1)
                        continue

                    if keyboard.is_pressed("alt+2") and (
                        not any([keyboard.is_pressed(key) for key in "abcdefgh"])
                    ):
                        self.clear_buffer()
                        self.update_status("[CANCELLED] Input cleared (Alt+2)")
                        break

                    if keyboard.is_pressed("alt+9") and (
                        not any([keyboard.is_pressed(key) for key in "abcdefgh"])
                    ):
                        self.update_status("[UNDO] Requesting undo...")
                        asyncio.run(self.send_undo())
                        self.clear_buffer()
                        time.sleep(0.3)
                        break

                    for key in "abcdefgh12345678":
                        if keyboard.is_pressed(key):
                            if key not in keys:
                                keys.append(key)
                                if len(keys) == 2:
                                    sq = "".join(keys[:2])
                                    if not self.from_sq:
                                        self.from_sq = sq
                                        self.update_status(
                                            f"[From] {self.from_sq}\n\nWaiting for next square...\nAlt + 9 = undo move, Alt + 2 = cancel"
                                        )
                                        time.sleep(0.25)
                                    elif not self.to_sq:
                                        self.to_sq = sq
                                        self.update_status(
                                            f"[To] {self.to_sq}\nAlt + 9 = undo move, Alt + 2 = cancel, Alt + ` = confirm"
                                        )
                                    keys.clear()
                                    if self.move_timer:
                                        self.move_timer.cancel()
                                    self.move_timer = threading.Timer(
                                        5, self.clear_buffer_timeout
                                    )
                                    self.move_timer.start()

                    if keyboard.is_pressed("alt+`"):
                        if (
                            self.from_sq
                            and self.to_sq
                            and (
                                (
                                    not self.first_move
                                    and self.side.get().lower() == "white"
                                )
                                or self.side.get().lower() == "black"
                            )
                        ):

                            self.first_move = False
                            move = self.from_sq + self.to_sq
                            self.processing = True
                            self.update_status(f"[Processing] {move}")
                            asyncio.run(self.send_move(move))
                            self.clear_buffer()
                        elif self.first_move:
                            if self.side.get().lower() == "white":
                                self.first_move = False
                                self.update_status("[Processing] White's first move")
                                asyncio.run(self.send_move(None))
                                self.clear_buffer()
                                time.sleep(0.25)
                            else:
                                self.update_status("[Error] Incomplete move")
                        elif not self.processing:
                            self.update_status("[Error] Incomplete move")
                            break

                    if keyboard.is_pressed("alt+p"):  # Support Alt + P too
                        asyncio.run(self.send_promotion())
                        break

                    time.sleep(0.1)
            time.sleep(0.05)

    def show_bot_selector(self):
        def confirm():
            index = bot_dropdown.current()
            level = level_scale.get() if self.bots[index].get("is_engine") else None
            asyncio.run(self.send_bot_selection(index, level))
            selector.destroy()
            self.listening = True

        selector = tk.Toplevel(self.root)
        selector.title("Select Bot")
        selector.configure(bg="black")
        selector.attributes("-topmost", True)
        tk.Label(selector, text="Choose bot:", bg="black", fg="white").pack(pady=4)
        bot_names = [
            b["name"] if b["is_engine"] else f"{b['name']}({b['rating']})"
            for b in self.bots
        ]
        bot_dropdown = ttk.Combobox(selector, values=bot_names, state="readonly")
        bot_dropdown.pack(pady=4)
        level_label = tk.Label(selector, text="Engine level:", bg="black", fg="white")
        level_scale = tk.Scale(
            selector, from_=1, to=25, orient="horizontal", bg="black", fg="white"
        )
        bot_dropdown.bind(
            "<<ComboboxSelected>>",
            lambda e: (
                (level_label.pack(pady=(4, 0)), level_scale.pack(pady=(0, 4)))
                if self.bots[bot_dropdown.current()].get("is_engine")
                else (level_label.pack_forget(), level_scale.pack_forget())
            ),
        )
        tk.Button(selector, text="Select", command=confirm).pack(pady=4)

    async def send_move(self, move):
        try:
            if self.ws:
                await self.ws.send(
                    json.dumps({"action": "next_move", "opponent_move": move})
                )
        except Exception as e:
            self.update_status(f"[WS ERROR] {e}")

    async def send_undo(self):
        if not self.ws:
            self.update_status("Not connected.")
            return

        await self.ws.send(json.dumps({"action": "undo"}))

    async def send_promotion(self):
        if not self.ws:
            self.update_status("Not connected.")
            return

        piece = simpledialog.askstring(
            "Promotion", "Promote to? (q, r, b, n):", parent=self.root
        )
        if piece and piece.lower() in ["q", "r", "b", "n"]:
            await self.ws.send(
                json.dumps({"action": "promote", "promote_to": piece.lower()})
            )
            self.update_status(f"Promotion sent: {piece.upper()}")
        else:
            self.update_status("Invalid promotion input.")

    async def send_bot_selection(self, bot_id, engine_level=None):
        if self.ws:
            payload = {"action": "select_bot", "bot_id": bot_id}
            if engine_level is not None:
                payload["engine_level"] = engine_level
            await self.ws.send(json.dumps(payload))

    def update_status(self, message):
        self.root.after(0, lambda: self.status.set(message))

    def on_close(self):
        answer = messagebox.askyesno("Exit", "Do you want to close this app?")
        if answer:
            self.root.destroy()
            os._exit(0)
        else:
            self.root.destroy()
            threading.Thread(target=run_gui, daemon=True).start()

    def run_websocket_loop(self):
        asyncio.run(self.websocket_loop())

    async def websocket_loop(self):
        try:
            async with websockets.connect(WS_URL) as websocket:
                self.ws = websocket
                await websocket.send(
                    json.dumps({"action": "init", "side": self.side.get()})
                )
                while True:
                    msg = await websocket.recv()
                    if str(msg).strip() == "":
                        continue
                    try:
                        data = json.loads(msg)
                        if "error" in data:
                            self.update_status("Error: " + data["error"])
                        elif "status" in data:
                            if data.get("type") == "init":
                                self.bots = data.get("bots", [])
                                current_bot = data.get("current_bot", {})
                                current_bot_name = current_bot.get("name", "Unknown")
                                current_bot_rating = current_bot.get("rating", "N/A")
                                current_bot = f"Current Bot: {current_bot_name} ({current_bot_rating})"
                                if data["side"] == "white":
                                    self.update_status(
                                        "Press Alt + ` to get suggestions."
                                        f"\n{current_bot}\n"
                                    )
                                else:
                                    self.update_status(
                                        "Copy opponent's move then press Alt + ` to get suggestions."
                                        f"\n{current_bot}\n"
                                    )

                            elif data.get("type") == "undo":
                                await asyncio.sleep(0.5)
                                initial_status = self.status.get()
                                self.update_status(data["status"])
                                await asyncio.sleep(3)
                                self.update_status(initial_status)
                            else:
                                initial_status = self.status.get().splitlines()[0]
                                self.update_status(data["status"])
                                await asyncio.sleep(3)
                                self.update_status(
                                    f"{initial_status}\n{data['status']}"
                                )
                        elif "move" in data:
                            move = data["move"]
                            display = f"{move['piece']} {move['from']}→{move['to']}"
                            self.update_status(f"Suggested: {display}")
                            self.processing = False
                    except Exception as e:
                        self.processing = False
                        print("[ERROR] Malformed WS data:", msg, e)
        except Exception as e:
            self.update_status("Disconnected")


def run_gui():
    root = tk.Tk()
    app = ChessClient(root)
    root.mainloop()
