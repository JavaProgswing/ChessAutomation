import PyInstaller.__main__
import os

def build_exe():
    print("Building ChessAutomation.exe...")
    
    PyInstaller.__main__.run([
        'chess_client.py',
        '--name=ChessAutomation',
        '--onefile',
        '--noconsole',
        '--clean',
        '--exclude-module=server',  # Exclude the server module if it exists as a python package
    ])
    
    print("Build complete. Executable is in the 'dist' folder.")

if __name__ == "__main__":
    build_exe()
