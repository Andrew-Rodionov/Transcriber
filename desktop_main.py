"""Entry point for the native desktop application."""
import multiprocessing


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        from desktop.app import main
        main()
    except Exception:
        from pathlib import Path
        import traceback
        import ctypes
        folder = Path(__file__).resolve().parent / ".desktop-data"
        folder.mkdir(exist_ok=True)
        log = folder / "desktop.log"
        log.write_text(traceback.format_exc(), encoding="utf-8")
        ctypes.windll.user32.MessageBoxW(None, f"Не удалось открыть T-BCM. Журнал: {log}", "T-BCM", 16)
