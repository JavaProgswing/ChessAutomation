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

        self.driver = Chrome(profile=self.profile, options=options)
        self.wait = WebDriverWait(self.driver, 15)

        self.initial_state = None
        self.pending_promotion = None
        self.open_analysis_and_start()
        self.selected_bot = self.get_current_bot()
        self.waiting_for_engine_move = False

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
        self.initial_state = self.get_initial_board_state()
        practice_button = self.driver.find_element(
            By.CSS_SELECTOR, 'button[aria-label="Practice vs Computer"]'
        )
        self.driver.execute_script("arguments[0].click();", practice_button)
        print("[INFO] Practice vs Computer button clicked.")

        self.driver.switch_to.window(self.driver.window_handles[-1])
        print("[INFO] Switched to new Practice tab.")

        self.wait.until(EC.presence_of_element_located((By.ID, "board-board")))

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

            scroll_container = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.bot-selection-scroll")
                )
            )

            seen_bots = set()
            ChessAutomator.BOTS.clear()

            # Scrolling loop
            first_bot = True
            while True:
                tiles = self.driver.find_elements(By.CSS_SELECTOR, "li.bot-component")
                for tile in tiles:
                    name = tile.get_attribute("data-bot-name")
                    if name in seen_bots:
                        continue

                    is_locked = tile.find_elements(
                        By.CSS_SELECTOR, "span.cc-icon-glyph.cc-icon-small.bot-lock"
                    )
                    if is_locked:
                        seen_bots.add(name)
                        continue

                    if not first_bot:
                        name_el = self.driver.find_element(
                            By.CSS_SELECTOR, "span.selected-bot-name"
                        )
                        initial_name = name_el.text.strip()

                        self.driver.execute_script("arguments[0].click();", tile)

                        self.wait.until(
                            lambda d: d.find_element(
                                By.CSS_SELECTOR, "span.selected-bot-name"
                            ).text.strip()
                            != initial_name
                        )

                    first_bot = False

                    classification = tile.get_attribute("data-bot-classification")
                    is_engine = classification.lower() == "engine"
                    avatar_url = None
                    try:
                        img_el = tile.find_element(By.CSS_SELECTOR, "img.bot-img")
                        avatar_url = img_el.get_attribute("src")
                    except:
                        avatar_url = None
                        print(f"[WARN] No avatar found for bot '{name}'")

                    if is_engine:
                        slider = self.wait.until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, 'input.slider-input[type="range"]')
                            )
                        )
                        self.set_slider_value(
                            self.driver,
                            slider,
                            int(slider.get_attribute("min")),
                        )
                        rating_start = self.driver.find_element(
                            By.CSS_SELECTOR, "span.selected-bot-rating"
                        ).text.strip("()")

                        self.set_slider_value(
                            self.driver,
                            slider,
                            int(slider.get_attribute("max")),
                        )
                        rating_end = self.driver.find_element(
                            By.CSS_SELECTOR, "span.selected-bot-rating"
                        ).text.strip("()")

                        name = f"Engine ({rating_start}-{rating_end})"

                        ChessAutomator.BOTS.append(
                            {
                                "id": len(ChessAutomator.BOTS),
                                "name": name,
                                "classification": classification.lower(),
                                "is_engine": is_engine,
                                "avatar": avatar_url,
                            }
                        )
                        seen_bots.add(name)
                    else:
                        rating = self.driver.find_element(
                            By.CSS_SELECTOR, "span.selected-bot-rating"
                        ).text.strip("()")

                        ChessAutomator.BOTS.append(
                            {
                                "id": len(ChessAutomator.BOTS),
                                "name": name,
                                "rating": rating,
                                "classification": classification.lower(),
                                "is_engine": is_engine,
                                "avatar": avatar_url,
                            }
                        )
                        seen_bots.add(name)

                # Scroll slowly
                self.driver.execute_script(
                    "arguments[0].scrollTop += 1200;", scroll_container
                )

                # Check if scrolled to bottom
                is_at_bottom = self.driver.execute_script(
                    """
                    let el = arguments[0];
                    return el.scrollTop + el.offsetHeight >= el.scrollHeight - 5;
                """,
                    scroll_container,
                )

                if is_at_bottom:
                    break

            # Click back button
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

    def set_slider_value(self, driver, slider_element, target_value):
        min_val = int(slider_element.get_attribute("min"))
        max_val = int(slider_element.get_attribute("max"))

        if not (min_val <= target_value <= max_val):
            raise ValueError(
                f"Value {target_value} is outside range {min_val}-{max_val}"
            )

        # Get current value of the slider
        current_value = int(
            driver.execute_script("return arguments[0].value;", slider_element)
        )

        # If the value is already set, skip
        if current_value == target_value:
            print(f"[INFO] Slider already at value {target_value}, no change needed.")
            return

        # Get current rating text before change
        rating_span = self.wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "span.selected-bot-rating")
            )
        )
        initial_rating = rating_span.text.strip()

        # Set new value via JS
        driver.execute_script(
            """
            const slider = arguments[0];
            const value = arguments[1];

            slider.value = value;
            slider.dispatchEvent(new Event('input', { bubbles: true }));
            slider.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            slider_element,
            target_value,
        )

        # Wait for the rating to change
        self.wait.until(
            lambda d: d.find_element(
                By.CSS_SELECTOR, "span.selected-bot-rating"
            ).text.strip()
            != initial_rating
        )
        print(f"[INFO] Slider value set to {target_value}")

    def select_bot(self, bot_id: int, engine_level: int | None = None):
        if not ChessAutomator.BOT_LOADED:
            print("[INFO] Loading bots list for the first time...")
            try:
                self.load_bot_list()
            except Exception as e:
                raise Exception(f"[ERROR] Failed to load bots: {e}")

        if bot_id < 0 or bot_id >= len(ChessAutomator.BOTS):
            raise ValueError(f"Bot ID {bot_id} is out of range.")

        bot_to_select = ChessAutomator.BOTS[bot_id]

        try:
            # Open the bot selection menu
            change_bot_button = self.wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[aria-label="Change Bot"]')
                )
            )
            self.driver.execute_script("arguments[0].click();", change_bot_button)

            scroll_container = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.bot-selection-scroll")
                )
            )

            selected_tile = None

            # Scroll through the bot list to find the correct tile
            while True:
                tiles = self.driver.find_elements(By.CSS_SELECTOR, "li.bot-component")

                for tile in tiles:
                    name = tile.get_attribute("data-bot-name")
                    classification = tile.get_attribute("data-bot-classification")

                    if (
                        name == bot_to_select["name"]
                        and classification.lower()
                        == bot_to_select.get("classification", "").lower()
                    ) or (
                        bot_to_select["is_engine"]
                        and classification.lower() == "engine"
                    ):
                        selected_tile = tile
                        break

                if selected_tile:
                    break

                # Scroll down
                self.driver.execute_script(
                    "arguments[0].scrollTop += 1200;", scroll_container
                )

                is_at_bottom = self.driver.execute_script(
                    """
                    let el = arguments[0];
                    return el.scrollTop + el.offsetHeight >= el.scrollHeight - 5;
                """,
                    scroll_container,
                )

                if is_at_bottom:
                    break  # Reached bottom without finding the bot

            if not selected_tile:
                raise Exception(
                    f"[ERROR] Could not find bot '{bot_to_select['name']}' in scroll list."
                )

            # Click the bot tile
            self.driver.execute_script("arguments[0].click();", selected_tile)
            print(f"[INFO] Bot tile clicked: {bot_to_select['name']}")

            # If it's an engine, set the slider
            if bot_to_select["is_engine"] and engine_level is not None:
                if not (1 <= engine_level <= 25):
                    raise ValueError(
                        f"Engine level must be between 1 and 25. Given: {engine_level}"
                    )

                slider_value = engine_level - 1  # Map level 1–25 → slider range 0–24

                slider = self.wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'input.slider-input[type="range"]')
                    )
                )

                self.set_slider_value(
                    self.driver, slider, slider_value
                )  # level 1–25 → value 0–24
                print(f"[INFO] Engine level set to {engine_level}")

            # Click Choose button
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

    def undo_last_move(self):
        """
        Clicks the undo button to revert the last move.
        """
        try:
            while self.waiting_for_engine_move:
                print("[INFO] Waiting for engine move to complete before undoing.")
                time.sleep(1)
            nodes = self.driver.find_elements(By.CSS_SELECTOR, "div.node")
            if len(nodes) < 2:
                print("[WARN] Not enough moves to undo.")
                return

            undo_button = self.wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[aria-label="Move Back"]')
                )
            )
            previous_state = self.get_board_state()
            ActionChains(self.driver).move_to_element(undo_button).click().perform()
            while True:
                current_state = self.get_board_state()
                if current_state != previous_state:
                    break
                else:
                    print("[INFO] Waiting for board to update after undo...")
                    time.sleep(0.5)

            undo_button = self.wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[aria-label="Move Back"]')
                )
            )
            ActionChains(self.driver).move_to_element(undo_button).click().perform()
            print("[INFO] Last move undone.")
        except Exception as e:
            raise Exception(f"[ERROR] Failed to undo last move: {e}")

    def get_initial_board_state(self) -> dict:
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
        pieces = self.driver.find_elements(
            By.CSS_SELECTOR, "#board-analysis-board .piece"
        )

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

    def save_board_state_to_file(self, board_state, filename="engine_debug.txt"):
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
        self.waiting_for_engine_move = True
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_state = self.get_board_state()

            removed_squares = [sq for sq in previous_state if sq not in current_state]
            added_squares = [sq for sq in current_state if sq not in previous_state]
            changed_squares = [
                sq
                for sq in current_state
                if sq in previous_state and current_state[sq] != previous_state[sq]
            ]

            # --- Detect Castling ---
            if len(removed_squares) == 2 and len(added_squares) == 2:
                moved_pieces = [previous_state[sq] for sq in removed_squares]
                if ("k", self.side.value) in moved_pieces and (
                    "r",
                    self.side.value,
                ) in moved_pieces:
                    king_from = next(
                        sq for sq in removed_squares if previous_state[sq][0] == "k"
                    )
                    king_to = next(
                        sq for sq in added_squares if current_state[sq][0] == "k"
                    )
                    print(
                        f"[CASTLING DETECTED] King moved from {self.square_index_to_alg(king_from)} to {self.square_index_to_alg(king_to)}"
                    )

                    self.waiting_for_engine_move = False
                    self.driver.save_screenshot("latest_move.png")
                    return {
                        "type": "castling",
                        "piece": "k",
                        "from": self.square_index_to_alg(king_from),
                        "to": self.square_index_to_alg(king_to),
                        "color": self.side.value,
                    }

            # --- Detect En Passant ---
            if len(removed_squares) == 2 and len(added_squares) == 1:
                capture_sq = removed_squares[0]
                pawn_sq = removed_squares[1]
                pawn = previous_state.get(pawn_sq)
                if pawn and pawn[0] == "p":
                    print("[EN PASSANT DETECTED]")

                    self.waiting_for_engine_move = False
                    self.driver.save_screenshot("latest_move.png")
                    return {
                        "type": "en_passant",
                        "piece": "p",
                        "from": self.square_index_to_alg(pawn_sq),
                        "to": self.square_index_to_alg(added_squares[0]),
                        "color": pawn[1],
                    }

            # --- Detect Normal or Capture Move ---
            if len(removed_squares) == 1 and (
                len(added_squares) == 1 or len(changed_squares) == 1
            ):
                from_sq = removed_squares[0]
                to_sq = added_squares[0] if added_squares else changed_squares[0]
                piece = previous_state[from_sq]
                print(
                    f"[ENGINE MOVE DETECTED] {piece[0].upper()} from {self.square_index_to_alg(from_sq)} to {self.square_index_to_alg(to_sq)}"
                )

                self.waiting_for_engine_move = False
                self.driver.save_screenshot("latest_move.png")
                return {
                    "piece": piece[0],
                    "from": self.square_index_to_alg(from_sq),
                    "to": self.square_index_to_alg(to_sq),
                    "color": piece[1],
                }

            time.sleep(0.5)

        print("[ERROR] Timeout waiting for engine move.")
        self.waiting_for_engine_move = False
        self.driver.save_screenshot("engine_timeout.png")
        self.save_board_state_to_file(previous_state, "engine_timeout_state.txt")
        self.save_board_state_to_file(
            self.get_board_state(), "engine_timeout_state_1.txt"
        )
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
            move = self.wait_for_engine_move(self.initial_state)
            return move

        print(f"[INFO] Simulating opponent move: {opponentMove}")
        before = self.simulate_opponent_move(opponentMove)

        print("[INFO] Capturing fresh board state after opponent move...")
        move = self.wait_for_engine_move(before)
        return move

    def simulate_board_state(self, state: dict, move: str) -> dict:
        """
        Simulates the effect of a move on a given board state.
        Does NOT apply promotion logic — pawn is just placed on the last rank as-is.

        Args:
            state (dict): Current board state as {square: (piece, color)}
            move (str): Move in algebraic notation like 'e2e4'

        Returns:
            dict: Updated board state
        """
        new_state = dict(state)

        from_alg = move[:2]
        to_alg = move[2:4]
        from_sq = self.alg_to_square_index(from_alg)
        to_sq = self.alg_to_square_index(to_alg)

        if from_sq not in new_state:
            raise ValueError(f"[SIMULATE] No piece at {from_alg} ({from_sq})")

        piece, color = new_state[from_sq]

        # --- Castling detection ---
        if piece == "k" and abs(ord(from_alg[0]) - ord(to_alg[0])) == 2:
            if to_alg[0] == "g":  # King-side
                rook_from = self.alg_to_square_index("h1" if color == "white" else "h8")
                rook_to = self.alg_to_square_index("f1" if color == "white" else "f8")
            else:  # Queen-side
                rook_from = self.alg_to_square_index("a1" if color == "white" else "a8")
                rook_to = self.alg_to_square_index("d1" if color == "white" else "d8")

            if rook_from in new_state:
                new_state[rook_to] = new_state.pop(rook_from)

        # --- En Passant ---
        if piece == "p" and from_alg[0] != to_alg[0] and to_sq not in new_state:
            capture_rank = (
                str(int(to_alg[1]) - 1) if color == "white" else str(int(to_alg[1]) + 1)
            )
            capture_alg = to_alg[0] + capture_rank
            capture_sq = self.alg_to_square_index(capture_alg)
            if capture_sq in new_state and new_state[capture_sq][0] == "p":
                del new_state[capture_sq]

        # Regular move
        new_state[to_sq] = (piece, color)
        del new_state[from_sq]

        return new_state

    def simulate_opponent_move(self, move: str):
        print(f"[INFO] Intended move: {move}")
        from_alg = move[:2]
        to_alg = move[2:]
        try:
            from_sq = self.alg_to_square_index(from_alg)
            to_sq = self.alg_to_square_index(to_alg)
        except ValueError:
            raise ValueError(f"Moves should be in chess notation like 'e2e4'")

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
            before = self.simulate_board_state(self.get_board_state(), move)
            ActionChains(self.driver).move_to_element(hint_el).click().perform()
            print(
                f"[INFO] Opponent move {from_alg} → {to_alg} completed via hint square."
            )
        except Exception as e:
            print(f"[ERROR] Failed to click hint square {to_alg}: {e}")
            raise ValueError(f"Cannot move own chess piece at {from_alg}.")

        # Check if promotion window appears and current from_alg is a pawn
        try:
            # WebDriverWait(self.driver, 1).until(
            #    EC.presence_of_element_located((By.CSS_SELECTOR, ".promotion-window")),
            # )
            promotion_window = self.driver.find_element(
                By.CSS_SELECTOR, ".promotion-window"
            )
            if not promotion_window:
                return before
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
        if len(alg) != 2 or alg[0] not in "abcdefgh" or alg[1] not in "12345678":
            raise ValueError(f"Invalid algebraic notation: {alg}")
        file = ord(alg[0]) - ord("a") + 1  # a=1, h=8
        rank = int(alg[1])  # 1-8
        return f"{file}{rank}"

    def square_index_to_alg(self, square_id: str) -> str:
        # Converts 88 → a8, 12 → h2, etc.
        col_map = {str(i): chr(97 + i - 1) for i in range(1, 9)}  # 1 → a, 8 → h
        row = square_id[1]
        col = square_id[0]
        return f"{col_map[col]}{row}"
