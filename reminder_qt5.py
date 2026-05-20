import datetime
import sys

from PyQt5.QtCore import QTimer, QDate
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QTextEdit,
    QPushButton, QListWidget, QSpinBox, QDateEdit,
    QFormLayout, QVBoxLayout, QHBoxLayout, QMessageBox
)
from winotify import Notification

DATE_FORMAT = "MM-dd-yyyy"
DATE_FORMAT_LITERAL = "%m-%d-%Y %H:%M"


# Notification
def fire_notification(title: str, message: str) -> None:
    toast = Notification(
        app_id="Reminder", title=title, msg=message or "From reminder.py"
    )
    toast.show()


# GUI
class ReminderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reminders")
        self.setFixedSize(360, 300)
        self._pending: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        now = datetime.datetime.now()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(8)

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat(DATE_FORMAT)
        form.addRow("Date", self.date_edit)

        # Time
        time_layout = QHBoxLayout()
        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setValue(now.hour)
        self.hour_spin.setFixedWidth(55)
        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 59)
        self.min_spin.setValue(now.minute)
        self.min_spin.setFixedWidth(55)
        self.hour_spin.setWrapping(True)
        self.min_spin.setWrapping(True)
        colon = QLabel(":")
        time_layout.addWidget(self.hour_spin)
        time_layout.addWidget(colon)
        time_layout.addWidget(self.min_spin)
        time_layout.addStretch()
        form.addRow("Time", time_layout)

        # Title
        self.title_edit = QLineEdit("Reminder")
        form.addRow("Title", self.title_edit)

        # Message
        self.msg_edit = QTextEdit()
        # self.msg_edit.setFixedHeight(70)
        form.addRow("Message", self.msg_edit)

        # Add top section to main layout
        main_layout.addLayout(form)

        # Button
        self.set_btn = QPushButton("Set Reminder")
        self.set_btn.clicked.connect(self._on_set)
        main_layout.addWidget(self.set_btn)

        # Status
        self.status_label = QLabel("Status: Waiting...")
        self.status_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.status_label)

        # Active reminders
        main_layout.addWidget(QLabel("Active reminders:"))
        self.list_widget = QListWidget()
        main_layout.addWidget(self.list_widget)

    def _on_set(self):
        try:
            qdate = self.date_edit.date()
            date_str = qdate.toString(DATE_FORMAT)
            hour = self.hour_spin.value()
            minute = self.min_spin.value()
            target_dt = datetime.datetime.strptime(
                f"{date_str} {hour:02d}:{minute:02d}", DATE_FORMAT_LITERAL
            )
        except ValueError:
            QMessageBox.critical(self, "Invalid input", "Could not parse the date/time.")
            return

        now = datetime.datetime.now()
        if target_dt <= now:
            QMessageBox.critical(self, "Past time", "Please choose a future date and time.")
            return

        delta_ms = int((target_dt - now).total_seconds() * 1000)

        title = self.title_edit.text().strip() or "Reminder"
        message = self.msg_edit.toPlainText().strip()
        label = f"{title}  →  {target_dt.strftime(DATE_FORMAT_LITERAL)}"

        self._pending.append({"label": label, "done": False})
        idx = len(self._pending) - 1
        self._refresh_list()

        secs = delta_ms // 1000
        mins, secs = divmod(secs, 60)
        self.status_label.setText(f"'{title}' fires in {mins}m {secs}s")

        timer = QTimer(self)
        timer.setSingleShot(True)

        def trigger():
            fire_notification(title, message)
            self._pending[idx]["done"] = True
            self._refresh_list()
            self.status_label.setText(f"'{title}' fired!")

        timer.timeout.connect(trigger)
        timer.start(delta_ms)

    def _refresh_list(self):
        self.list_widget.clear()
        for r in self._pending:
            tick = "Done" if r["done"] else "Waiting"
            self.list_widget.addItem(f"{tick}:  {r['label']}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ReminderApp()
    window.show()
    sys.exit(app.exec_())