import datetime
import sys

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
        self.date_edit.setDisplayFormat("yyyy-MM-dd")

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
        """Validate and return form values, or None on error."""
        try:
            qdate = self.date_edit.date()
            date_str = qdate.toString("yyyy-MM-dd")
            hour = self.hour_spin.value()
            minute = self.min_spin.value()
            target_dt = datetime.datetime.strptime(
                f"{date_str} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M"
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
        self._pending: list[dict] = (
            []
        )  # each entry: {title, message, target_dt, done, timer}
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(8)

        # Add button
        self.add_btn = QPushButton("+ Add Reminder")
        self.add_btn.clicked.connect(self._on_add)
        main_layout.addWidget(self.add_btn)

        # Status
        self.status_label = QLabel("Status: Waiting...")
        self.status_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.status_label)

        # Active reminders list
        main_layout.addWidget(QLabel("Active reminders:"))
        self.list_widget = QListWidget()
        main_layout.addWidget(self.list_widget)

        # Edit / Delete buttons
        btn_layout = QHBoxLayout()
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._on_edit)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        main_layout.addLayout(btn_layout)

    # Helpers
    def _schedule(self, idx: int) -> None:
        """Start a QTimer for the reminder at idx."""
        reminder = self._pending[idx]
        delta_ms = int(
            (reminder["target_dt"] - datetime.datetime.now()).total_seconds() * 1000
        )

        timer = QTimer(self)
        timer.setSingleShot(True)

        def trigger():
            fire_notification(reminder["title"], reminder["message"])
            self._pending[idx]["done"] = True
            self._refresh_list()
            self.status_label.setText(f"'{reminder['title']}' fired!")

        timer.timeout.connect(trigger)
        timer.start(delta_ms)
        self._pending[idx]["timer"] = timer

    def _refresh_list(self):
        self.list_widget.clear()
        for r in self._pending:
            tick = "Done" if r["done"] else "Waiting"
            self.list_widget.addItem(
                f"{tick}:  {r['title']}  →  {r['target_dt'].strftime('%Y-%m-%d %H:%M')}"
            )

    def _selected_idx(self) -> int | None:
        """Return the index of the selected list item, or None."""
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

        self._pending.append({**values, "done": False, "timer": None})
        idx = len(self._pending) - 1
        self._schedule(idx)
        self._refresh_list()

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
        if reminder["done"]:
            QMessageBox.information(
                self, "Already fired", "Cannot edit a reminder that has already fired."
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

        self._pending[idx] = {**values, "done": False, "timer": None}
        self._schedule(idx)
        self._refresh_list()

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
        self.status_label.setText("Reminder deleted.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ReminderApp()
    window.show()
    sys.exit(app.exec_())
