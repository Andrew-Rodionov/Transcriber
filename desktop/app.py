"""Native Tk interface; model imports stay in the owned worker process."""
import multiprocessing as mp
import os
from pathlib import Path
from queue import Empty
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from desktop.engine import Settings
from desktop.worker import run_worker
from desktop.process_tree import WorkerJob

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ".desktop-data"
WORD_DIR = ROOT / "WORD_FILE"


class Application:
    def __init__(self, root):
        self.root = root
        self.process = None
        self.worker_job = None
        self.tasks = self.events = None
        self.jobs = {}
        self.counter = 0
        self.closing = False
        DATA.mkdir(exist_ok=True)
        root.title("T-BCM — расшифровка записей")
        root.geometry("1000x660")
        root.minsize(960, 540)
        root.protocol("WM_DELETE_WINDOW", self.close)
        panel = ttk.Frame(root, padding=18)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="Расшифровка с разделением говорящих", font=("Segoe UI", 17)).pack(anchor="w")
        ttk.Label(panel, text="Добавьте записи и нажмите «Запустить очередь». Результат — Word с временными метками.").pack(anchor="w", pady=(4, 14))
        options = ttk.Frame(panel)
        options.pack(fill="x")
        self.model = tk.StringVar(value=Settings().model)
        self.language = tk.StringVar(value="ru")
        self.controls = []
        for label, variable, choices in (
                ("Модель", self.model, ("small", "medium", "large-v3")),
                ("Язык", self.language, ("ru", "auto", "en"))):
            ttk.Label(options, text=label).pack(side="left", padx=(0, 6))
            control = ttk.Combobox(options, textvariable=variable, values=choices, state="readonly", width=13)
            control.pack(side="left", padx=(0, 16))
            self.controls.append(control)
        ttk.Label(options, text="Обработка на CPU").pack(side="left")
        ttk.Style(root).configure("Action.TButton", padding=(12, 10), font=("Segoe UI", 10))
        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(16, 14))
        for column, (text, command) in enumerate((
                ("Добавить файлы", self.add_files),
                ("Запустить очередь", self.start_queue),
                ("Остановить очередь", self.stop),
                ("Папка результатов", self.open_output))):
            buttons.columnconfigure(column, weight=1, uniform="actions")
            button = ttk.Button(buttons, text=text, command=command, style="Action.TButton")
            button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))
        self.table = ttk.Treeview(panel, columns=("file", "state"), show="headings", selectmode="browse")
        self.table.heading("file", text="Запись")
        self.table.heading("state", text="Состояние")
        self.table.column("file", width=300)
        self.table.column("state", width=560)
        self.table.pack(fill="both", expand=True)
        self.table.bind("<Double-1>", lambda event: self.show_selected_status())
        self.progress = ttk.Progressbar(panel, maximum=100)
        self.progress.pack(fill="x", pady=(12, 6))
        self.status = tk.StringVar(value="Добавьте файлы. Обработка начнётся после нажатия «Запустить очередь».")
        ttk.Label(panel, textvariable=self.status, wraplength=920).pack(anchor="w")
        self.poll_timer = root.after(150, self.poll)

    def add_files(self):
        paths = filedialog.askopenfilenames(title="Выберите записи", filetypes=[
            ("Аудио и видео", "*.wav *.mp3 *.m4a *.flac *.ogg *.opus *.mp4 *.mkv *.wma *.aac *.webm"),
            ("Все файлы", "*.*")])
        if not paths:
            return
        for path in paths:
            self.counter += 1
            job = str(self.counter)
            self.jobs[job] = {"source": path, "state": "Ожидает запуска", "output": None, "status": "pending"}
            self.table.insert("", "end", iid=job, values=(Path(path).name, "Ожидает запуска"))
        self.status.set(f"Добавлено файлов: {len(paths)}. Нажмите «Запустить очередь», чтобы обработать их.")

    def start_queue(self):
        pending = [(job, data) for job, data in self.jobs.items() if data["status"] == "pending"]
        if not pending:
            self.status.set("Нет файлов, ожидающих запуска. Добавьте записи в очередь.")
            return
        token = os.getenv("HF_TOKEN", "").strip()
        if self.process is None and not token:
            messagebox.showerror("Нужен доступ к диаризации",
                                 "Задайте HF_TOKEN в файле .env в папке программы и перезапустите приложение.")
            return
        try:
            WORD_DIR.mkdir(parents=True, exist_ok=True)
            if self.process is None:
                self.tasks, self.events = mp.Queue(), mp.Queue()
                settings = Settings(model=self.model.get(), language=self.language.get(),
                                    token=token, output_dir=str(WORD_DIR),
                                    cache_dir=str(DATA / "models"))
                self.process = mp.Process(target=run_worker, args=(self.tasks, self.events, settings,
                                          str(DATA / "worker.log")), daemon=True)
                self.process.start()
                self.worker_job = WorkerJob(self.process.pid)
                for control in self.controls:
                    control.configure(state="disabled")
            for job, data in pending:
                self.tasks.put((job, data["source"]))
                data["status"] = "submitted"
                self.update(job, "В очереди")
            self.status.set(f"В обработку передано файлов: {len(pending)}.")
        except Exception as error:
            self.stop()
            messagebox.showerror("Не удалось запустить очередь", str(error))

    def update(self, job, state):
        self.jobs[job]["state"] = state
        self.table.item(job, values=(Path(self.jobs[job]["source"]).name, state))

    def poll(self):
        if self.closing:
            return
        if self.events is not None:
            try:
                while True:
                    kind, job, *data = self.events.get_nowait()
                    if kind == "started":
                        self.update(job, "Обработка")
                        self.progress["value"] = 0
                    elif kind == "stage":
                        self.update(job, data[0])
                        self.status.set(data[0])
                        self.progress["value"] = data[1]
                    elif kind == "done":
                        self.jobs[job]["output"] = data[0]
                        self.jobs[job]["status"] = "done"
                        self.update(job, "Готово — документ сохранён в WORD_FILE")
                        self.progress["value"] = 100
                        self.status.set(f"Сохранено: {data[0]}")
                    elif kind == "error":
                        self.jobs[job]["status"] = "error"
                        self.update(job, "Ошибка: " + data[0])
                        self.status.set("Ошибка обработки. Дважды нажмите на строку для подробностей.")
            except Empty:
                pass
        if self.process is not None and not self.process.is_alive():
            self.stop(f"Процесс обработки завершился (код {self.process.exitcode}). См. .desktop-data/worker.log")
        self.poll_timer = self.root.after(150, self.poll)

    def stop(self, reason="Остановлено пользователем"):
        if self.worker_job is not None:
            self.worker_job.close()
            self.worker_job = None
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=2)
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(timeout=2)
            else:
                self.process.join()
            self.process.close()
            self.process = None
        for channel in (self.tasks, self.events):
            if channel is not None:
                channel.cancel_join_thread()
                channel.close()
        self.tasks = self.events = None
        for job, data in self.jobs.items():
            if data["status"] == "submitted":
                data["status"] = "cancelled"
                self.update(job, reason)
        for control in self.controls:
            control.configure(state="readonly" if isinstance(control, ttk.Combobox) else "normal")
        self.status.set(reason + ". Добавьте файлы и нажмите «Запустить очередь».")
        self.progress["value"] = 0

    def show_selected_status(self):
        selection = self.table.selection()
        if selection:
            data = self.jobs[selection[0]]
            messagebox.showinfo("Состояние записи", data["state"])

    def open_path(self, path):
        try:
            os.startfile(path)
        except OSError as error:
            messagebox.showerror("Не удалось открыть", str(error))

    def open_output(self):
        try:
            WORD_DIR.mkdir(parents=True, exist_ok=True)
            # Open the whole directory, without selecting or filtering a job's file.
            self.open_path(str(WORD_DIR))
        except OSError as error:
            messagebox.showerror("Не удалось открыть папку результатов", str(error))

    def close(self):
        self.closing = True
        self.root.after_cancel(self.poll_timer)
        self.stop()
        self.root.destroy()


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    root = tk.Tk()
    Application(root)
    root.mainloop()
