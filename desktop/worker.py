"""One FIFO consumer, one reusable model session, no HTTP server."""
from pathlib import Path
import logging
import os
import traceback

from desktop.engine import ModelSession, Settings
from desktop.network import configure_tls, error_message


def run_worker(tasks, events, settings: Settings, log_path: str):
    # Configure these before importing the model libraries.
    os.environ["HF_HOME"] = str(Path(settings.cache_dir) / "huggingface")
    os.environ["TORCH_HOME"] = str(Path(settings.cache_dir) / "torch")
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    logging.basicConfig(filename=log_path, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", force=True)
    # pythonw has no stdout/stderr. Some dependencies still write progress to them.
    import sys
    stream = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = stream
    current = None

    def notify(stage, progress):
        events.put(("stage", current, stage, progress))

    session = ModelSession(settings, notify)
    while True:
        task = tasks.get()
        if task is None:
            break
        current, source = task
        events.put(("started", current))
        try:
            # Injection is idempotent and must precede the first model import.
            configure_tls()
            output = session.process(Path(source))
            events.put(("done", current, str(output)))
        except Exception as error:
            logging.error("Transcription failed for %s\n%s", source, traceback.format_exc())
            # Do not put credentials or a full dependency traceback into the UI.
            events.put(("error", current, error_message(error, settings.token)))
        finally:
            # Preserve models, release temporary tensors/arrays left by failed stages.
            import gc
            gc.collect()
