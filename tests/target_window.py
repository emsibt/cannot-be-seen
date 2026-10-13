"""A detached Win32 window used as a stand-in for 'some other app'.

    python tests/target_window.py [title]
"""

import sys
import tkinter as tk

TITLE = sys.argv[1] if len(sys.argv) > 1 else "CBS-TEST-TARGET"

root = tk.Tk()
root.title(TITLE)
root.geometry("460x200+140+140")
tk.Label(root, text=TITLE, font=("Segoe UI", 14)).pack(expand=True)
root.mainloop()
