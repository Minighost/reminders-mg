"""
reminder.py — Set a one-shot Windows desktop notification for a future datetime.
"""

import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from tkcalendar import DateEntry
from plyer import notification


# Notification
def fire_notification(title: str, message: str) -> None:
    notification.notify(
        title=title,
        message=message or "From reminder.py",
        app_name="Reminders",
        timeout=15, # seconds the toast stays visible
    )


# GUI
class ReminderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Reminders")
        self.resizable(False, False)
        self.geometry("320x420")
        self._build_ui()
        self._pending: list[dict] = [] # track active reminders

    # Layout
    def _build_ui(self):
        now = datetime.datetime.now()

        # Helpers
        def row(pady=(4, 0)):
            f = tk.Frame(self)
            f.pack(fill="x", padx=14, pady=pady)
            return f

        def label(parent, text, top_align=False, pady=(0, 0)):
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
        r = row()
        self.status_var = tk.StringVar(value="Status: Waiting...")
        tk.Label(r, textvariable=self.status_var, fg="gray").pack(
            side="left", expand=True
        )

        # Active reminders
        r = row(pady=(4, 2))
        tk.Label(r, text="Active reminders", font=("", 9, "bold")).pack(side="left")

        r = row(pady=(0, 12))
        self.list_var = tk.StringVar()
        tk.Listbox(r, listvariable=self.list_var, height=11, font=("", 9)).pack(
            side="left", fill="both", expand=True
        )

    # Actions
    def _on_set(self):
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

        now = datetime.datetime.now()
        if target_dt <= now:
            messagebox.showerror("Past time", "Please choose a future date and time.")
            return

        delta_ms = int((target_dt - now).total_seconds() * 1000)

        title = self.title_var.get().strip() or "Reminder"
        message = self.msg_text.get("1.0", "end").strip()
        label = f"{title}  →  {target_dt.strftime('%Y-%m-%d %H:%M')}"

        self._pending.append({"label": label, "done": False})
        idx = len(self._pending) - 1
        self._refresh_list()

        # update status immediately
        secs = delta_ms // 1000
        mins, secs = divmod(secs, 60)
        self.status_var.set(f"'{title}' fires in {mins}m {secs}s")

        # schedule notification
        def trigger():
            fire_notification(title, message)
            self._pending[idx]["done"] = True
            self._refresh_list()
            self.status_var.set(f"'{title}' fired!")

        self.after(delta_ms, trigger)

    def _refresh_list(self):
        items = []
        for r in self._pending:
            tick = "Done" if r["done"] else "Waiting"
            items.append(f"{tick}:  {r['label']}")
        self.list_var.set(items)


if __name__ == "__main__":
    app = ReminderApp()
    app.mainloop()
