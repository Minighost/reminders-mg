A simple reminder app for desktop. Developed and tested on Windows 11, I have no idea if this works in Linux.

Kind of like [SimpleReminder](https://f-droid.org/packages/felixwiemuth.simplereminder/) for Android, the concept is to set some reminders that do not need to be synced, but need to persist throughout sessions.

Originally built with TKinter, but switched to QT5, because I think it looks better (and it's also way easier to use).

You can build and use the app using pyinstaller:

`pyinstaller --onefile --noconsole reminder.py`