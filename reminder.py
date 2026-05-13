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
        self._build_ui()
        self._pending: list[dict] = []  # track active reminders

    # Layout

    def _build_ui(self):
        pad = dict(padx=10, pady=6)

        # Date row
        tk.Label(self, text="Date").grid(row=0, column=0, sticky="e", **pad)
        self.date_entry = DateEntry(
            self,
            width=12,
            date_pattern="yyyy-mm-dd",
            firstweekday="sunday",
            showweeknumbers=False,
        )
        self.date_entry.grid(row=0, column=1, columnspan=3, sticky="w", **pad)

        # Time row
        tk.Label(self, text="Time").grid(row=1, column=0, sticky="e", **pad)

        now = datetime.datetime.now()
        self.hour_var = tk.StringVar(value=f"{now.hour:02d}")
        self.min_var = tk.StringVar(value=f"{now.minute:02d}")

        hour_spin = ttk.Spinbox(
            self,
            from_=0,
            to=23,
            width=4,
            format="%02.0f",
            textvariable=self.hour_var,
            wrap=True,
        )
        hour_spin.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=6)

        tk.Label(self, text=":").grid(row=1, column=2)

        min_spin = ttk.Spinbox(
            self,
            from_=0,
            to=59,
            width=4,
            format="%02.0f",
            textvariable=self.min_var,
            wrap=True,
        )
        min_spin.grid(row=1, column=3, sticky="w", padx=(0, 10), pady=6)

        # Title row
        tk.Label(self, text="Title").grid(row=2, column=0, sticky="e", **pad)
        self.title_var = tk.StringVar(value="Reminder")
        tk.Entry(self, textvariable=self.title_var, width=28).grid(
            row=2, column=1, columnspan=3, sticky="ew", **pad
        )

        # Message row
        tk.Label(self, text="Message").grid(
            row=3, column=0, sticky="ne", padx=10, pady=6
        )
        self.msg_text = tk.Text(self, width=28, height=3, wrap="word")
        self.msg_text.grid(row=3, column=1, columnspan=3, sticky="ew", **pad)

        # Status / countdown
        self.status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.status_var, fg="gray", font=("", 9)).grid(
            row=4, column=0, columnspan=4, pady=(0, 4)
        )

        # Button
        ttk.Button(self, text="Set Reminder", command=self._on_set).grid(
            row=5, column=0, columnspan=4, pady=(0, 12)
        )

        # Active reminders list
        tk.Label(self, text="Active reminders", font=("", 9, "bold")).grid(
            row=6, column=0, columnspan=4, sticky="w", padx=10
        )

        self.list_var = tk.StringVar()
        tk.Listbox(
            self, listvariable=self.list_var, height=4, width=40, font=("", 9)
        ).grid(row=7, column=0, columnspan=4, padx=10, pady=(0, 10))

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
            self.status_var.set(f"⏰  '{title}' fires in {mins}m {secs}s")

        def on_done():
            self._pending[idx]["done"] = True
            self._refresh_list()
            self.status_var.set(f"✔  '{title}' fired!")

        schedule(target_dt, title, message, on_start, on_done)

    def _refresh_list(self):
        items = []
        for r in self._pending:
            tick = "✔" if r["done"] else "⏳"
            items.append(f"{tick}  {r['label']}")
        self.list_var.set(items)


if __name__ == "__main__":
    app = ReminderApp()
    app.mainloop()
