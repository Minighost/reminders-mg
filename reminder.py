import datetime
import json
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QDate
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
from PyQt5.QtGui import QIcon

DATE_FORMAT = "MM-dd-yyyy"
DATE_FORMAT_LITERAL = "%m-%d-%Y %H:%M"

if getattr(sys, "frozen", False):
    # Running as PyInstaller EXE
    BASE_DIR = Path(sys.executable).parent
else:
    # Running as script
    BASE_DIR = Path(__file__).parent
SAVE_FILE = BASE_DIR / "reminders.json"


# Override QSpinBox for zero-padded time selection
class PaddedSpinBox(QSpinBox):
    def textFromValue(self, value: int) -> str:
        return f"{value:02d}"


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
        self.hour_spin = PaddedSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setFixedWidth(55)
        self.hour_spin.setWrapping(True)
        self.min_spin = PaddedSpinBox()
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


# Notification Pop-up - Similar to Outlook's notification style
class NotificationWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(300, 200)
        self.setWindowTitle("Reminders")
        # self.setWindowFlags(Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._list = QListWidget()
        self._list.setWordWrap(True)
        self._list.setSpacing(2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(self._list)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.right() - self.width() - 10,
            screen.bottom() - self.height() - 40,
        )

    def notify(self, title: str, message: str) -> None:
        text = title if not message else f"{title}: {message}"
        self._list.addItem(text)
        self.show()
        QApplication.alert(self)  # make taskbar icon flash

    # Override close event
    def closeEvent(self, event):
        self._list.clear()
        QApplication.alert(self, 0)
        event.accept()


# Main window
class ReminderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reminders")
        self.setFixedSize(360, 340)
        self._pending: list[dict] = []
        self._notif_window = NotificationWindow()
        self._build_ui()
        self._load()

        # use a "watchdog" to trigger reminders. this prevents reminders from triggering
        # at incorrect times after computer sleep.
        # caveat: 30 seconds of "error" for reminders
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(30_000)  # check every 30 seconds
        # might need tighter timing? not sure how this impacts CPU usage
        self._watchdog.timeout.connect(self._check_reminders)
        self._watchdog.start()
        self._check_reminders()  # immediately check reminders on startup

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
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
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
                self.status_label.setText(
                    "Exception occurred while loading reminders from json!"
                )
                return  # if there's an exception, list'll be empty anyway
                # maybe it's better to do `raw = []`? idk

            now = datetime.datetime.now()
            for entry in raw:
                try:
                    target_dt = datetime.datetime.fromisoformat(entry["target_dt"])
                except (KeyError, ValueError):
                    continue

                saved_status = entry.get("status", "missed")
                if saved_status == "waiting" and target_dt <= now:
                    saved_status = "missed"

                self._pending.append(
                    {
                        "title": entry.get("title", "Reminder"),
                        "message": entry.get("message", ""),
                        "target_dt": target_dt,
                        "status": saved_status,
                    }
                )

        missed = [r for r in self._pending if r["status"] == "missed"]
        self._refresh_list()

        if missed:
            self.status_label.setText(f"{len(missed)} reminder(s) missed while closed!")
        else:
            self.status_label.setText(f"{len(self._pending)} reminder(s) loaded.")

    def _save(self):
        to_save = [
            {
                "title": r["title"],
                "message": r["message"],
                "target_dt": r["target_dt"].isoformat(),
                "status": r["status"],
            }
            for r in self._pending
        ]
        SAVE_FILE.write_text(json.dumps(to_save, indent=4), encoding="utf-8")

    # Helpers
    def _check_reminders(self):
        now = datetime.datetime.now()
        fired_any = False
        for r in self._pending:
            if r["status"] == "waiting" and r["target_dt"] <= now:
                r["status"] = "done"
                self._notif_window.notify(r["title"], r["message"])
                self.status_label.setText(f"'{r['title']}' fired!")
                fired_any = True
        if fired_any:
            self._refresh_list()
            self._save()

    def _refresh_list(self):
        self.list_widget.clear()
        for r in self._pending:
            status = {"waiting": "Waiting", "done": "Done", "missed": "Missed"}[
                r["status"]
            ]
            self.list_widget.addItem(
                f"{status}:  {r['title']}  →  {r['target_dt'].strftime(DATE_FORMAT_LITERAL)}"
            )

    # Actions
    def _on_add(self):
        dlg = ReminderDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        values = dlg.get_values()
        if values is None:
            return

        self._pending.append({**values, "status": "waiting"})
        self._refresh_list()
        self._save()

        mins, secs = divmod(
            int((values["target_dt"] - datetime.datetime.now()).total_seconds()), 60
        )
        self.status_label.setText(f"'{values['title']}' fires in {mins}m {secs}s")

    def _on_edit(self):
        selected_reminders = self.list_widget.selectedItems()
        if not selected_reminders:
            QMessageBox.information(
                self, "No selection", "Please select a reminder to edit."
            )
            return
        if len(selected_reminders) > 1:
            QMessageBox.information(
                self, "Too many selected", "Please select only 1 reminder to edit."
            )
            return

        idx = self.list_widget.row(selected_reminders[0])
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

        self._pending[idx] = {**values, "status": "waiting"}
        self._refresh_list()
        self._save()

        mins, secs = divmod(
            int((values["target_dt"] - datetime.datetime.now()).total_seconds()), 60
        )
        self.status_label.setText(
            f"'{values['title']}' updated, fires in {mins}m {secs}s"
        )

    def _on_delete(self):
        selected_reminders = self.list_widget.selectedItems()
        if not selected_reminders:
            QMessageBox.information(
                self, "No selection", "Please select a reminder to delete."
            )
            return

        # reminders must be deleted from last to first, so the indices of the list do not shift
        indices = sorted(
            [self.list_widget.row(item) for item in selected_reminders], reverse=True
        )

        confirm = QMessageBox.question(
            self,
            "Delete reminder(s)",
            f"Delete {len(indices)} reminder(s)?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        for idx in indices:
            self._pending.pop(idx)

        self._refresh_list()
        self._save()
        self.status_label.setText(f"{len(indices)} reminder(s) deleted.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("reminder_icon.ico"))
    window = ReminderApp()
    window.show()
    sys.exit(app.exec_())
