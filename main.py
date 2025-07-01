from chess_client import run_uvicorn, run_gui
import threading

if __name__ == "__main__":
    # Start the Uvicorn server in a separate thread
    server_thread = threading.Thread(target=run_uvicorn)
    server_thread.start()

    # Start the Tkinter GUI
    run_gui()

    # Wait for the server thread to finish
    server_thread.join()
