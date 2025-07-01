import traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from chess import ChessAutomator, ChessSide
from typing import Dict
import json
import asyncio
import concurrent.futures
import time
import uvicorn

app = FastAPI()
connections: Dict[str, WebSocket] = {}


@app.get("/ping")
async def ping():
    return {"status": "Ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = str(id(websocket))
    connections[client_id] = websocket
    print(f"[WS] Client {client_id} connected.")

    chess_bot = None
    executor = concurrent.futures.ThreadPoolExecutor()

    async def keep_alive():
        try:
            while True:
                await asyncio.sleep(10)
                await websocket.send_text(" ")
        except Exception:
            pass

    keepalive_task = asyncio.create_task(keep_alive())

    try:
        while True:
            try:
                data = await websocket.receive_text()
                data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON format."})
                continue
            except Exception as e:
                await websocket.send_json({"error": f"Receive error: {str(e)}"})
                continue

            action = data.get("action")

            if action == "init":
                side = data.get("side", "white").lower()
                if side not in ["white", "black"]:
                    await websocket.send_json({"error": "Invalid side."})
                    continue

                start_time = time.time()
                chess_bot = await asyncio.get_event_loop().run_in_executor(
                    executor,
                    lambda: ChessAutomator(
                        ChessSide.WHITE if side == "white" else ChessSide.BLACK
                    ),
                )

                # Get bot list and current bot after loading
                if not ChessAutomator.BOT_LOADED:
                    await asyncio.get_event_loop().run_in_executor(
                        executor, lambda: chess_bot.load_bot_list()
                    )
                bots = [
                    {
                        "id": b["id"],
                        "name": b["name"],
                        "rating": b.get("rating", None),
                        "avatar": b.get("avatar", None),
                        "is_engine": b["is_engine"],
                    }
                    for b in ChessAutomator.BOTS
                ]
                current = await asyncio.get_event_loop().run_in_executor(
                    executor, lambda: chess_bot.selected_bot
                )
                print(f"Initialization took {(time.time() - start_time):.2f} seconds.")

                await websocket.send_json(
                    {
                        "status": f"Initialized as {side.upper()}.",
                        "type": "init",
                        "side": side.lower(),
                        "bots": bots,
                        "current_bot": current,
                    }
                )

            elif action == "next_move":
                if not chess_bot:
                    await websocket.send_json({"error": "Bot not initialized."})
                    continue

                opponent_move = data.get("opponent_move")
                try:
                    move = await asyncio.get_event_loop().run_in_executor(
                        executor, lambda: chess_bot.getNextBestMove(opponent_move)
                    )
                    await websocket.send_json({"move": move})
                except Exception as e:
                    traceback.print_exc()
                    await websocket.send_json({"error": str(e)})

            elif action == "promote":
                piece = data.get("promote_to", "q")
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        executor, lambda: chess_bot.complete_promotion(piece)
                    )
                    await websocket.send_json(
                        {
                            "status": f"Promoted to {piece.upper()}",
                            "type": "promote",
                            "piece": piece,
                        }
                    )
                except Exception as e:
                    await websocket.send_json({"error": str(e)})
            elif action == "select_bot":
                bot_id = data.get("bot_id", 0)
                engine_level = data.get("engine_level", None)
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        executor, lambda: chess_bot.select_bot(bot_id, engine_level)
                    )

                    await websocket.send_json(
                        {
                            "status": f"Selected bot: {chess_bot.selected_bot['name']} ({chess_bot.selected_bot['rating']})",
                            "type": "select_bot",
                            "current_bot": chess_bot.selected_bot,
                        }
                    )
                except Exception as e:
                    await websocket.send_json({"error": str(e)})

            else:
                await websocket.send_json({"error": "Unknown action."})

    except (WebSocketDisconnect, RuntimeError):
        del connections[client_id]
        print(f"[WS] Client {client_id} disconnected.")
    finally:
        keepalive_task.cancel()
        executor.shutdown(wait=False)
        print(f"[WS] Connection for client {client_id} closed.")


def run_uvicorn():
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
