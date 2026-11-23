"""A persistent model session. Imported only in the processing subprocess."""
from dataclasses import dataclass
from pathlib import Path
import subprocess

from desktop.transcript import build_turns
from desktop.word_export import export_word


@dataclass(frozen=True)
class Settings:
    model: str = "small"
    language: str = "ru"
    device: str = "cpu"
    token: str = ""
    output_dir: str = ""
    cache_dir: str = ""


class ModelSession:
    def __init__(self, settings: Settings, notify):
        self.settings = settings
        self.notify = notify
        self.asr = None
        self.diarizer = None
        self.aligner = None
        self.align_language = None

    def _audio(self, source: Path):
        import imageio_ffmpeg
        import numpy as np
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-threads", "1",
                   "-i", str(source), "-f", "s16le", "-ac", "1", "-acodec",
                   "pcm_s16le", "-ar", "16000", "-"]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise RuntimeError("Не удалось прочитать аудио: " + result.stderr.decode("utf-8", "replace")[-1200:])
        return np.frombuffer(result.stdout, np.int16).astype(np.float32) / 32768.0

    def process(self, source: Path) -> Path:
        import torch
        import whisperx
        from whisperx.diarize import DiarizationPipeline

        settings = self.settings
        if settings.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("NVIDIA/CUDA недоступна. Выберите CPU и перезапустите очередь.")
        self.notify("Чтение аудио", 5)
        audio = self._audio(source)
        duration = len(audio) / 16000
        if not len(audio):
            raise RuntimeError("Аудиофайл пуст.")
        if self.asr is None:
            self.notify("Идёт подготовка модели распознавания. Пожалуйста, подождите", 10)
            self.asr = whisperx.load_model(
                settings.model, device=settings.device,
                compute_type="float16" if settings.device == "cuda" else "int8",
                language=None if settings.language == "auto" else settings.language,
                download_root=str(Path(settings.cache_dir) / "whisper"),
            )
        self.notify("Распознавание речи", 20)
        with torch.inference_mode():
            result = self.asr.transcribe(audio, batch_size=4)
        language = result.get("language", settings.language)
        if not result.get("segments"):
            self.notify("Сохранение Word", 95)
            return export_word(source, Path(settings.output_dir), [], language, duration, settings.model)
        if self.align_language != language:
            # Only the current language's aligner is cached, so mixed queues stay bounded.
            self.aligner = None
            self.align_language = None
            self.notify("Идёт подготовка модели временных меток. Пожалуйста, подождите", 45)
            self.aligner = whisperx.load_align_model(language_code=language, device="cpu",
                                                    model_dir=str(Path(settings.cache_dir) / "alignment"))
            self.align_language = language
        self.notify("Определение временных меток", 50)
        with torch.inference_mode():
            aligned = whisperx.align(result["segments"], *self.aligner, audio, device="cpu",
                                     return_char_alignments=False)
        if self.diarizer is None:
            self.notify("Идёт подготовка модели разделения говорящих. Пожалуйста, подождите", 65)
            self.diarizer = DiarizationPipeline(token=settings.token or None, device="cpu",
                                                cache_dir=str(Path(settings.cache_dir) / "diarization"))
        self.notify("Разделение говорящих", 70)
        with torch.inference_mode():
            speakers = self.diarizer(audio)
            labelled = whisperx.assign_word_speakers(speakers, aligned)
        self.notify("Сохранение Word", 95)
        return export_word(source, Path(settings.output_dir), build_turns(labelled["segments"]),
                           language, duration, settings.model)
