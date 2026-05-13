"""
reminder.py — Set a one-shot Windows desktop notification for a future datetime.

Dependencies:
    pip install tkcalendar plyer

Usage:
    python reminder.py
"""

import threading
import time
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from tkcalendar import DateEntry
except ImportError:
    raise SystemExit("Missing dependency: pip install tkcalendar")

try:
    from plyer import notification
except ImportError:
    raise SystemExit("Missing dependency: pip install plyer")


# Notification
def fire_notification(title: str, message: str) -> None:
    notification.notify(
        title=title,
        message=message or "Time's up!",
        app_name="Reminder",
        timeout=15,  # seconds the toast stays visible
    )


# Background sleep thread
def schedule(
    target_dt: datetime.datetime, title: str, message: str, on_start, on_done
) -> None:
    """Sleep until target_dt in a daemon thread, then fire the notification."""
    delta = (target_dt - datetime.datetime.now()).total_seconds()

    def _run():
        on_start(delta)
        time.sleep(delta)
        fire_notification(title, message)
        on_done()

    t = threading.Thread(target=_run, daemon=True)
    t.start()


# GUI
class ReminderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Reminders")
        self.resizable(False, False)
        self.geometry("320x320")
        self._build_ui()
        self._pending: list[dict] = []  # track active reminders

    # Layout
    def _build_ui(self):
        now = datetime.datetime.now()

        # Helpers
        def row(pady=(4, 0)):
            """A full-width frame for one logical row."""
            f = tk.Frame(self)
            f.pack(fill="x", padx=14, pady=pady)
            return f

        def label(parent, text, top_align=False, pady=(0, 0)):
            """Right-aligned label that lines up with the input widgets."""
            anchor = "ne" if top_align else "e"
            tk.Label(parent, text=text, width=8, anchor=anchor).pack(
                side="left", pady=pady
            )

        # Date
        r = row()
        label(r, "Date", pady=(10, 0))
        self.date_entry = DateEntry(
            r,
            width=12,
            date_pattern="yyyy-mm-dd",
            firstweekday="sunday",
            showweeknumbers=False,
        )
        self.date_entry.pack(side="left", padx=(6, 0), pady=(10, 0))

        # Time
        r = row()
        label(r, "Time")
        self.hour_var = tk.StringVar(value=f"{now.hour:02d}")
        self.min_var = tk.StringVar(value=f"{now.minute:02d}")
        ttk.Spinbox(
            r,
            from_=0,
            to=23,
            width=4,
            format="%02.0f",
            textvariable=self.hour_var,
            wrap=True,
        ).pack(side="left", padx=(6, 0))
        tk.Label(r, text=":").pack(side="left", padx=3)
        ttk.Spinbox(
            r,
            from_=0,
            to=59,
            width=4,
            format="%02.0f",
            textvariable=self.min_var,
            wrap=True,
        ).pack(side="left")

        # Title
        r = row()
        label(r, "Title")
        self.title_var = tk.StringVar(value="Reminder")
        tk.Entry(r, textvariable=self.title_var).pack(
            side="left", fill="x", expand=True, padx=(6, 10)
        )

        # Message
        r = row()
        label(r, "Message", top_align=True)
        self.msg_text = tk.Text(r, height=3, wrap="word")
        self.msg_text.pack(side="left", fill="x", expand=True, padx=(6, 10))

        # Button
        r = row(pady=(6, 6))
        ttk.Button(r, text="Set Reminder", command=self._on_set).pack(
            side="left", expand=True
        )

        # Status
        r = row(pady=(0, 0))
        self.status_var = tk.StringVar(value="Status: Waiting...")
        tk.Label(r, textvariable=self.status_var, fg="gray", font=("", 9)).pack(
            side="left", padx=(0, 0), expand=True
        )

        # Active reminders
        r = row(pady=(4, 2))
        tk.Label(r, text="Active reminders", font=("", 9, "bold")).pack(side="left")

        r = row(pady=(0, 12))
        self.list_var = tk.StringVar()
        tk.Listbox(r, listvariable=self.list_var, height=4, font=("", 9)).pack(
            side="left", fill="x", expand=True
        )

    # Actions
    def _on_set(self):

        # Parse datetime
        try:
            date_str = self.date_entry.get_date().strftime("%Y-%m-%d")
            hour = int(self.hour_var.get())
            minute = int(self.min_var.get())
            target_dt = datetime.datetime.strptime(
                f"{date_str} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M"
            )
        except ValueError:
            messagebox.showerror("Invalid input", "Could not parse the date/time.")
            return

        if target_dt <= datetime.datetime.now():
            messagebox.showerror("Past time", "Please choose a future date and time.")
            return

        title = self.title_var.get().strip() or "Reminder"
        message = self.msg_text.get("1.0", "end").strip()
        label = f"{title}  →  {target_dt.strftime('%Y-%m-%d %H:%M')}"

        self._pending.append({"label": label, "done": False})
        idx = len(self._pending) - 1
        self._refresh_list()

        def on_start(delta_secs):
            mins = int(delta_secs // 60)
            secs = int(delta_secs % 60)
            self.status_var.set(f"'{title}' fires in {mins}m {secs}s")

        def on_done():
            self._pending[idx]["done"] = True
            self._refresh_list()
            self.status_var.set(f"'{title}' fired!")

        schedule(target_dt, title, message, on_start, on_done)

    def _refresh_list(self):
        items = []
        for r in self._pending:
            tick = "Done" if r["done"] else "Waiting"
            items.append(f"{tick}:  {r['label']}")
        self.list_var.set(items)


if __name__ == "__main__":
    app = ReminderApp()
    app.mainloop()
