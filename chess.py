from enum import Enum
from selenium.webdriver import ActionChains
from selenium_profiles.webdriver import Chrome
from selenium_profiles.profiles import profiles
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
import time


class ChessSide(Enum):
    WHITE = "white"
    BLACK = "black"


class ChessAutomator:
    BOTS = []  # Shared bot list across all instances (only metadata)
    BOT_LOADED = False

    def __init__(self, side: ChessSide):
        self.side = side
        self.profile = profiles.Windows()
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--mute-audio")
        options.add_argument("--disable-gpu")

        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.managed_default_content_settings.images": 2,
        }
        prefs = {}
        options.add_experimental_option("prefs", prefs)
        self.driver = Chrome(profile=self.profile, options=options)
        self.wait = WebDriverWait(self.driver, 15)

        self.initial_state = None
        self.pending_promotion = None
        self.open_analysis_and_start()
        self.selected_bot = self.get_current_bot()

    def open_analysis_and_start(self):
        self.driver.get("https://www.chess.com/analysis?tab=analysis")
        self.wait.until(
            EC.presence_of_element_located((By.ID, "board-controls-settings"))
        )
        print("[INFO] Analysis page loaded.")

        if self.side == ChessSide.WHITE:
            print("[INFO] Flipping board so engine plays black and user plays white.")
            settings_button = self.driver.find_element(By.ID, "board-controls-settings")
            ActionChains(self.driver).move_to_element(settings_button).perform()
            self.wait.until(
                EC.presence_of_element_located((By.ID, "board-controls-flip"))
            )
            flip_button = self.driver.find_element(By.ID, "board-controls-flip")
            self.driver.execute_script("arguments[0].click();", flip_button)
            print("[INFO] Board flipped.")

        self.wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'button[aria-label="Practice vs Computer"]')
            )
        )
        practice_button = self.driver.find_element(
            By.CSS_SELECTOR, 'button[aria-label="Practice vs Computer"]'
        )
        self.driver.execute_script("arguments[0].click();", practice_button)
        print("[INFO] Practice vs Computer button clicked.")

        self.driver.switch_to.window(self.driver.window_handles[-1])
        print("[INFO] Switched to new Practice tab.")

        self.wait.until(EC.presence_of_element_located((By.ID, "board-board")))
        self.initial_state = self.get_board_state()

    def load_bot_list(self):
        if ChessAutomator.BOT_LOADED:
            return

        try:
            change_bot_button = self.wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[aria-label="Change Bot"]')
                )
            )
            self.driver.execute_script("arguments[0].click();", change_bot_button)

            self.wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "li.bot-component")
                )
            )
            tiles = self.driver.find_elements(By.CSS_SELECTOR, "li.bot-component")

            ChessAutomator.BOTS.clear()

            for i, tile in enumerate(tiles):
                if tile.find_elements(
                    By.CSS_SELECTOR, "span.cc-icon-glyph.cc-icon-small.bot-lock"
                ):
                    continue

                name = tile.get_attribute("data-bot-name")
                classification = tile.get_attribute("data-bot-classification")
                is_engine = classification.lower() == "engine"
                avatar_url = None
                try:
                    img_el = tile.find_element(By.CSS_SELECTOR, "img.bot-img")
                    avatar_url = img_el.get_attribute("src")
                except:
                    pass

                ChessAutomator.BOTS.append(
                    {
                        "id": len(ChessAutomator.BOTS),
                        "name": name,
                        "is_engine": is_engine,
                        "avatar": avatar_url,
                    }
                )

            # ✅ Click back button so no bot is changed
            try:
                back_button = self.driver.find_element(
                    By.CSS_SELECTOR, "button.selection-menu-back"
                )
                self.driver.execute_script("arguments[0].click();", back_button)
            except:
                pass

            ChessAutomator.BOT_LOADED = True
            print(f"[INFO] {len(ChessAutomator.BOTS)} bots loaded.")
        except Exception as e:
            raise Exception(f"[ERROR] Failed to load bot list: {e}")

    def select_bot(self, bot_id: int, engine_level: int | None = None):
        if not ChessAutomator.BOT_LOADED:
            print("[INFO] Loading bots list for the first time...")
            try:
                self.load_bot_list()
            except Exception as e:
                raise Exception(f"[ERROR] Failed to load bots: {e}")

        if bot_id < 0 or bot_id >= len(ChessAutomator.BOTS):
            raise ValueError(f"Bot ID {bot_id} is out of range.")

        try:
            change_bot_button = self.wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[aria-label="Change Bot"]')
                )
            )
            self.driver.execute_script("arguments[0].click();", change_bot_button)

            self.wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "li.bot-component")
                )
            )
            tiles = self.driver.find_elements(By.CSS_SELECTOR, "li.bot-component")

            selected_index = 0
            for i, tile in enumerate(tiles):
                name = tile.get_attribute("data-bot-name")
                if name == ChessAutomator.BOTS[bot_id]["name"]:
                    selected_index = i
                    break

            selected_tile = tiles[selected_index]
            self.driver.execute_script("arguments[0].click();", selected_tile)
            print(f"[INFO] Bot tile clicked: {ChessAutomator.BOTS[bot_id]['name']}")

            if ChessAutomator.BOTS[bot_id]["is_engine"] and engine_level is not None:
                slider = self.wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'input[type="range"]')
                    )
                )
                self.driver.execute_script(
                    f"""
                    arguments[0].value = {engine_level};
                    arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                    arguments[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                """,
                    slider,
                )
                print(f"[INFO] Engine level set to {engine_level}")

            choose_button = self.wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        '//button[contains(@class, "cc-button-primary")]//span[text()="Choose"]/ancestor::button',
                    )
                )
            )
            self.driver.execute_script("arguments[0].click();", choose_button)
            print("[INFO] Bot selection confirmed.")

            self.selected_bot = self.get_current_bot()

        except Exception as e:
            raise Exception(f"[ERROR] Failed to select bot: {e}")

    def get_current_bot(self):
        try:
            container = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "player-row-component"))
            )
            name_el = container.find_element(
                By.CSS_SELECTOR, '[data-test-element="user-tagline-username"]'
            )
            rating_el = container.find_element(By.CLASS_NAME, "cc-user-rating-white")
            return {
                "name": name_el.text.strip(),
                "rating": rating_el.text.strip().strip("()"),
            }
        except Exception as e:
            print(f"[WARN] Failed to fetch current bot info: {e}")
            return None

    def get_board_state(self) -> dict:
        """
        Parses the current board and returns a dict like:
        {
            "88": ("r", "black"),
            "12": ("p", "white"),
            ...
        }
        where keys are 'square-XY' IDs (like "88", "12") and values are (piece type, color)
        """
        board = {}
        pieces = self.driver.find_elements(By.CSS_SELECTOR, "#board-board .piece")

        for piece in pieces:
            classes = piece.get_attribute("class").split()
            piece_type = None
            color = None
            square = None

            for cls in classes:
                if cls.startswith("w"):
                    color = "white"
                    piece_type = cls[1]  # p, r, n, b, q, k
                elif cls.startswith("b"):
                    color = "black"
                    piece_type = cls[1]
                elif cls.startswith("square-"):
                    square = cls.split("-")[1]

            if piece_type and color and square:
                board[square] = (piece_type, color)

        return board

    def print_board_state(self):
        board_state = self.get_board_state()

        # Optional: sort squares in board order
        def square_sort_key(sq):
            # Sort by rank 8 to 1, file a to h
            file = sq[0]
            rank = int(sq[1])
            return (8 - rank) * 8 + ord(file) - ord("a")

        sorted_squares = sorted(
            board_state.keys(),
            key=lambda s: square_sort_key(self.square_index_to_alg(s)),
        )

        print("\n[BOARD STATE]")
        for square in sorted_squares:
            piece, color = board_state[square]
            print(f"{self.square_index_to_alg(square)}: {color} {piece}")
        print()

    def save_board_state_to_file(self, filename="engine_debug.txt"):
        board_state = self.get_board_state()

        def square_sort_key(sq):
            file = sq[0]
            rank = int(sq[1])
            return (8 - rank) * 8 + ord(file) - ord("a")

        sorted_squares = sorted(
            board_state.keys(),
            key=lambda s: square_sort_key(self.square_index_to_alg(s)),
        )

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("[BOARD STATE]\n")
                for square in sorted_squares:
                    piece, color = board_state[square]
                    f.write(f"{self.square_index_to_alg(square)}: {color} {piece}\n")
            print(f"[DEBUG] Board state saved to {filename}")
        except Exception as e:
            print(f"[ERROR] Could not write board state to file: {e}")

    def wait_for_engine_move(self, previous_state: dict, timeout: int = 35):
        print("[INFO] Waiting for engine move...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            current_state = self.get_board_state()

            removed_square = None
            added_square = None
            moved_piece = None

            for square in previous_state:
                if square not in current_state:
                    removed_square = square
                    moved_piece = previous_state[square]
                    break

            for square in current_state:
                if square not in previous_state:
                    added_square = square
                    break

            if removed_square and added_square and moved_piece:
                from_alg = self.square_index_to_alg(removed_square)
                to_alg = self.square_index_to_alg(added_square)
                piece_type, color = moved_piece

                print(
                    f"[ENGINE MOVE DETECTED - {time.time()-start_time}s] {piece_type.upper()} from {from_alg} to {to_alg}"
                )
                return {
                    "piece": piece_type,
                    "from": from_alg,
                    "to": to_alg,
                    "color": color,
                }

            time.sleep(0.5)

        print("[ERROR] Timeout waiting for engine move.")
        self.driver.save_screenshot("engine_timeout.png")
        self.save_board_state_to_file("engine_timeout_state.txt")
        raise TimeoutException("No move detected within the timeout period.")

    def complete_promotion(self, promote_to: str = "q"):
        if not self.pending_promotion:
            raise Exception("No pending promotion to complete.")

        selector_map = {
            "q": ".promotion-piece.wq, .promotion-piece.bq",
            "r": ".promotion-piece.wr, .promotion-piece.br",
            "b": ".promotion-piece.wb, .promotion-piece.bb",
            "n": ".promotion-piece.wn, .promotion-piece.bn",
        }

        if promote_to not in selector_map:
            raise ValueError(
                "Invalid piece for promotion. Use one of: 'q', 'r', 'b', 'n'"
            )

        try:
            piece_button = self.driver.find_element(
                By.CSS_SELECTOR, selector_map[promote_to]
            )
            piece_button.click()
            print(f"[PROMOTION COMPLETE] Promoted to {promote_to.upper()}")
        except Exception as e:
            raise Exception(f"[ERROR] Failed to complete promotion: {e}")

        self.pending_promotion = None

    def getNextBestMove(self, opponentMove: str | None):
        if self.pending_promotion:
            raise Exception(
                "[ERROR] Pending promotion detected. Complete it using complete_promotion() before proceeding."
            )

        if opponentMove is None:
            if self.side == ChessSide.BLACK:
                raise ValueError("opponentMove cannot be None when playing Black.")
            print("[INFO] Capturing board state before engine move...")
            move = self.wait_for_engine_move(self.initial_state)
            return move

        print(f"[INFO] Simulating opponent move: {opponentMove}")
        before = self.simulate_opponent_move(opponentMove)

        print("[INFO] Capturing fresh board state after opponent move...")
        move = self.wait_for_engine_move(before)
        return move

    def simulate_opponent_move(self, move: str):
        print(f"[INFO] Intended move: {move}")
        from_alg = move[:2]
        to_alg = move[2:]

        from_sq = self.alg_to_square_index(from_alg)
        to_sq = self.alg_to_square_index(to_alg)

        try:
            piece_el = self.driver.find_element(
                By.CSS_SELECTOR, f".piece.square-{from_sq}"
            )
            print(f"[DEBUG] Found piece at {from_alg} (square-{from_sq})")
        except Exception as e:
            print(f"[ERROR] Could not find piece at {from_alg}: {e}")
            raise ValueError(f"No chess pieces at {from_alg}.")

        # Click the piece to activate valid hints
        ActionChains(self.driver).move_to_element(piece_el).click().perform()

        try:
            # Wait for either a normal move hint or a capture hint
            hint_el = WebDriverWait(self.driver, 3).until(
                lambda d: (
                    d.find_element(By.CSS_SELECTOR, f".hint.square-{to_sq}")
                    if len(d.find_elements(By.CSS_SELECTOR, f".hint.square-{to_sq}"))
                    > 0
                    else (
                        d.find_element(By.CSS_SELECTOR, f".capture-hint.square-{to_sq}")
                        if len(
                            d.find_elements(
                                By.CSS_SELECTOR, f".capture-hint.square-{to_sq}"
                            )
                        )
                        > 0
                        else None
                    )
                )
            )

            # Click the move or capture hint
            ActionChains(self.driver).move_to_element(hint_el).click().perform()
            print(
                f"[INFO] Opponent move {from_alg} → {to_alg} completed via hint square."
            )
        except Exception as e:
            print(f"[ERROR] Failed to click hint square {to_alg}: {e}")
            raise ValueError(f"Cannot move own chess piece at {from_alg}.")

        before = self.get_board_state()
        # Check if promotion window appears and current from_alg is a pawn
        try:
            WebDriverWait(self.driver, 1).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".promotion-window")),
            )
            self.pending_promotion = {
                "from": from_alg,
                "to": to_alg,
                "color": "black" if self.side == ChessSide.WHITE else "white",
            }
            print(
                f"[PROMOTION DETECTED] Promotion required at {to_alg}. Waiting for completion."
            )
        except:
            pass  # No promotion
        return before

    def alg_to_square_index(self, alg: str) -> str:
        """
        Converts 'e4' → '54' (i.e. .square-54)
        a-h maps to 1-8 (left to right)
        8-1 maps to 8-1 (top to bottom)
        """
        file = ord(alg[0]) - ord("a") + 1  # a=1, h=8
        rank = int(alg[1])  # 1-8
        return f"{file}{rank}"

    def square_index_to_alg(self, square_id: str) -> str:
        # Converts 88 → a8, 12 → h2, etc.
        col_map = {str(i): chr(97 + i - 1) for i in range(1, 9)}  # 1 → a, 8 → h
        row = square_id[1]
        col = square_id[0]
        return f"{col_map[col]}{row}"
