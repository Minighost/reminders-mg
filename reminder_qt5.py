import datetime
import json
import sys
from pathlib import Path

from PyQt5.QtCore import QTimer, QDate
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QListWidget,
    QSpinBox,
    QDateEdit,
    QFormLayout,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
)
from winotify import Notification

DATE_FORMAT = "MM-dd-yyyy"
DATE_FORMAT_LITERAL = "%m-%d-%Y %H:%M"
SAVE_FILE = Path(__file__).parent / "reminders.json"


# Notification
def fire_notification(title: str, message: str) -> None:
    toast = Notification(
        app_id="Reminder", title=title, msg=message or "From reminder.py"
    )
    toast.show()


# Edit dialog - reused for both new and existing reminders
class ReminderDialog(QDialog):
    def __init__(self, parent=None, reminder: dict = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Reminder" if reminder else "New Reminder")
        self.setFixedWidth(320)

        now = datetime.datetime.now()
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat(DATE_FORMAT)

        # Time
        time_layout = QHBoxLayout()
        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setFixedWidth(55)
        self.hour_spin.setWrapping(True)
        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 59)
        self.min_spin.setFixedWidth(55)
        self.min_spin.setWrapping(True)
        time_layout.addWidget(self.hour_spin)
        time_layout.addWidget(QLabel(":"))
        time_layout.addWidget(self.min_spin)
        time_layout.addStretch()

        # Title
        self.title_edit = QLineEdit()

        # Message
        self.msg_edit = QTextEdit()
        self.msg_edit.setFixedHeight(70)

        form.addRow("Date", self.date_edit)
        form.addRow("Time", time_layout)
        form.addRow("Title", self.title_edit)
        form.addRow("Message", self.msg_edit)
        layout.addLayout(form)

        # Populate fields from existing reminder or defaults
        if reminder:
            dt: datetime.datetime = reminder["target_dt"]
            self.date_edit.setDate(QDate(dt.year, dt.month, dt.day))
            self.hour_spin.setValue(dt.hour)
            self.min_spin.setValue(dt.minute)
            self.title_edit.setText(reminder["title"])
            self.msg_edit.setPlainText(reminder["message"])
        else:
            self.date_edit.setDate(QDate.currentDate())
            self.hour_spin.setValue(now.hour)
            self.min_spin.setValue(now.minute)
            self.title_edit.setText("Reminder")

        # OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> dict | None:
        try:
            date_str = self.date_edit.date().toString(DATE_FORMAT)
            target_dt = datetime.datetime.strptime(
                f"{date_str} {self.hour_spin.value():02d}:{self.min_spin.value():02d}",
                DATE_FORMAT_LITERAL,
            )
        except ValueError:
            QMessageBox.critical(
                self, "Invalid input", "Could not parse the date/time."
            )
            return None

        if target_dt <= datetime.datetime.now():
            QMessageBox.critical(
                self, "Past time", "Please choose a future date and time."
            )
            return None

        return {
            "target_dt": target_dt,
            "title": self.title_edit.text().strip() or "Reminder",
            "message": self.msg_edit.toPlainText().strip(),
        }


# Main window
class ReminderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reminders")
        self.setFixedSize(360, 340)
        self._pending: list[dict] = []
        self._build_ui()
        self._load()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(8)

        self.add_btn = QPushButton("+ Add Reminder")
        self.add_btn.clicked.connect(self._on_add)
        main_layout.addWidget(self.add_btn)

        self.status_label = QLabel("Status: Waiting...")
        self.status_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.status_label)

        main_layout.addWidget(QLabel("Reminders:"))
        self.list_widget = QListWidget()
        main_layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._on_edit)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        main_layout.addLayout(btn_layout)

    # Persistence
    def _load(self):
        self._pending = []
        if SAVE_FILE.exists():
            try:
                raw = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
            except Exception as e:  # unsure what exceptions are possible here
                self.status_label.setText("Exception occurred while loading reminders from json!")
                return # if there's an exception, list'll be empty anyway
                # maybe it's better to do `raw = []`? idk

            now = datetime.datetime.now()
            for entry in raw:
                try:
                    target_dt = datetime.datetime.fromisoformat(entry["target_dt"])
                except (KeyError, ValueError):
                    continue

                status = "missed" if target_dt <= now else "waiting"
                self._pending.append(
                    {
                        "title": entry.get("title", "Reminder"),
                        "message": entry.get("message", ""),
                        "target_dt": target_dt,
                        "status": status,
                        "timer": None,
                    }
                )

        missed = [r for r in self._pending if r["status"] == "missed"]
        waiting = [r for r in self._pending if r["status"] == "waiting"]

        for i, r in enumerate(self._pending):
            if r["status"] == "waiting":
                self._schedule(i)

        self._refresh_list()

        if missed:
            names = ", ".join(f"'{r['title']}'" for r in missed)
            self.status_label.setText(f"Missed while closed: {names}")
        elif waiting:
            self.status_label.setText(f"{len(waiting)} reminder(s) loaded.")

    def _save(self):
        to_save = [
            {
                "title": r["title"],
                "message": r["message"],
                "target_dt": r["target_dt"].isoformat(),
            }
            for r in self._pending
            if r["status"] != "done"  # don't persist completed reminders
        ]
        SAVE_FILE.write_text(json.dumps(to_save, indent=4), encoding="utf-8")

    # Helpers
    def _schedule(self, idx: int) -> None:
        reminder = self._pending[idx]
        delta_ms = int(
            (reminder["target_dt"] - datetime.datetime.now()).total_seconds() * 1000
        )

        timer = QTimer(self)
        timer.setSingleShot(True)

        def trigger():
            fire_notification(reminder["title"], reminder["message"])
            self._pending[idx]["status"] = "done"
            self._refresh_list()
            self._save()
            self.status_label.setText(f"'{reminder['title']}' fired!")

        timer.timeout.connect(trigger)
        timer.start(delta_ms)
        self._pending[idx]["timer"] = timer

    def _refresh_list(self):
        self.list_widget.clear()
        for r in self._pending:
            status = {"waiting": "Waiting", "done": "Done", "missed": "Missed"}[
                r["status"]
            ]
            self.list_widget.addItem(
                f"{status}:  {r['title']}  →  {r['target_dt'].strftime(DATE_FORMAT_LITERAL)}"
            )

    def _selected_idx(self) -> int | None:
        row = self.list_widget.currentRow()
        return row if row >= 0 else None

    # Actions
    def _on_add(self):
        dlg = ReminderDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        values = dlg.get_values()
        if values is None:
            return

        self._pending.append({**values, "status": "waiting", "timer": None})
        idx = len(self._pending) - 1
        self._schedule(idx)
        self._refresh_list()
        self._save()

        mins, secs = divmod(
            int((values["target_dt"] - datetime.datetime.now()).total_seconds()), 60
        )
        self.status_label.setText(f"'{values['title']}' fires in {mins}m {secs}s")

    def _on_edit(self):
        idx = self._selected_idx()
        if idx is None:
            QMessageBox.information(
                self, "No selection", "Please select a reminder to edit."
            )
            return

        reminder = self._pending[idx]
        if reminder["status"] != "waiting":
            QMessageBox.information(
                self,
                "Cannot edit",
                f"This reminder has status '{reminder['status']}' and cannot be edited.",
            )
            return

        dlg = ReminderDialog(self, reminder)
        if dlg.exec_() != QDialog.Accepted:
            return
        values = dlg.get_values()
        if values is None:
            return

        # Cancel old timer and reschedule
        if reminder["timer"]:
            reminder["timer"].stop()

        self._pending[idx] = {**values, "status": "waiting", "timer": None}
        self._schedule(idx)
        self._refresh_list()
        self._save()

        mins, secs = divmod(
            int((values["target_dt"] - datetime.datetime.now()).total_seconds()), 60
        )
        self.status_label.setText(
            f"'{values['title']}' updated, fires in {mins}m {secs}s"
        )

    def _on_delete(self):
        idx = self._selected_idx()
        if idx is None:
            QMessageBox.information(
                self, "No selection", "Please select a reminder to delete."
            )
            return

        reminder = self._pending[idx]
        confirm = QMessageBox.question(
            self,
            "Delete reminder",
            f"Delete '{reminder['title']}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        if reminder["timer"]:
            reminder["timer"].stop()

        self._pending.pop(idx)
        self._refresh_list()
        self._save()
        self.status_label.setText("Reminder deleted.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ReminderApp()
    window.show()
    sys.exit(app.exec_())
