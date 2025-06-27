from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from chess import ChessAutomator, ChessSide
from typing import Dict
import json
import asyncio
import concurrent.futures

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

    # Create a separate ChessAutomator instance for this connection
    chess_bot = None

    # ThreadPoolExecutor for blocking operations
    executor = concurrent.futures.ThreadPoolExecutor()

    # Keep-alive coroutine
    async def keep_alive():
        try:
            while True:
                await asyncio.sleep(10)
                await websocket.send_text(" ")
        except Exception:
            pass  # Ignore keepalive send errors

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

                # Create automator instance for the selected side
                chess_bot = await asyncio.get_event_loop().run_in_executor(
                    executor,
                    lambda: ChessAutomator(
                        ChessSide.WHITE if side == "white" else ChessSide.BLACK
                    ),
                )
                await websocket.send_json(
                    {
                        "status": f"Initialized as {side.upper()}.",
                        "type": "init",
                        "side": side.lower(),
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

            else:
                await websocket.send_json({"error": "Unknown action."})

    except (WebSocketDisconnect, RuntimeError):
        del connections[client_id]
        print(f"[WS] Client {client_id} disconnected.")
    finally:
        keepalive_task.cancel()
        executor.shutdown(wait=False)
        print(f"[WS] Connection for client {client_id} closed.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
