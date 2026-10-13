"""
Keeps references to running QThreads so they aren't garbage collected.
"""
from PyQt6.QtCore import QThread, QObject, pyqtSignal


_active_threads = []


def run_in_thread(fn, callback):
    """Run fn() in a background QThread, deliver result to callback on main thread."""

    class Worker(QObject):
        done = pyqtSignal(object)

        def run(self):
            self.done.emit(fn())

    thread = QThread()
    worker = Worker()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.done.connect(callback)
    worker.done.connect(thread.quit)

    def _cleanup():
        if thread in _active_threads:
            _active_threads.remove(thread)

    thread.finished.connect(_cleanup)
    thread.finished.connect(thread.deleteLater)

    # Hold a reference until the thread finishes
    thread._worker = worker
    _active_threads.append(thread)
    thread.start()
