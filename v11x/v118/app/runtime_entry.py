# Auto-extracted from app/legacy_runtime.py during one-iteration runtime split
from app.runtime_support import *
from interface.gui.legacy_gui_runtime import MainWindow

def install_exception_logging() -> None:
    def _write_crash_block(title: str, body: str) -> None:
        try:
            with CRASH_LOG.open("a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {title}\n{body}\n")
        except Exception:
            pass

    def _hook(exc_type, exc_value, exc_tb):
        formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.critical("Unhandled exception:\n%s", formatted)
        record_runtime_error("sys.excepthook", "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb), traceback_text=formatted)
        _write_crash_block("sys.excepthook", formatted)
        log_heartbeat("crash", "sys_excepthook", error=str(exc_value))
        traceback.print_exception(exc_type, exc_value, exc_tb)
        try:
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Ошибка GUI")
            msg.setText(str(exc_value))
            msg.setDetailedText(formatted)
            msg.exec()
        except Exception:
            pass

    def _thread_hook(args):
        formatted = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        logging.critical("Unhandled thread exception in %s:\n%s", getattr(args.thread, "name", "thread"), formatted)
        record_runtime_error(f"threading.excepthook:{getattr(args.thread, 'name', 'thread')}", "Unhandled thread exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback), traceback_text=formatted)
        _write_crash_block(f"threading.excepthook:{getattr(args.thread, 'name', 'thread')}", formatted)
        log_heartbeat("crash", "thread_excepthook", thread=getattr(args.thread, "name", "thread"), error=str(args.exc_value))

    def _unraisable_hook(unraisable):
        err = getattr(unraisable, "exc_value", None)
        formatted = "".join(traceback.format_exception(getattr(unraisable, "exc_type", type(err)), err, getattr(unraisable, "exc_traceback", None)))
        logging.critical("Unraisable exception: %s", formatted)
        record_runtime_error("sys.unraisablehook", "Unraisable exception", traceback_text=formatted, message=str(err or ""))
        _write_crash_block("sys.unraisablehook", formatted)
        log_heartbeat("crash", "unraisable", error=str(err))

    sys.excepthook = _hook
    threading.excepthook = _thread_hook
    sys.unraisablehook = _unraisable_hook

def main() -> None:
    setup_logging()
    log_heartbeat("app", "startup", version=APP_VERSION)
    app = QApplication(sys.argv)
    install_exception_logging()
    window = MainWindow()
    window.show()
    exit_code = app.exec()
    log_heartbeat("app", "shutdown", exit_code=exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
