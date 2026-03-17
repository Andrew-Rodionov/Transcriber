import whisperx
import time
import gc
import torch
import os
from dotenv import load_dotenv
import json
from typing import Optional, Dict, Any, List, Union, Tuple
from dataclasses import dataclass
from pathlib import Path


load_dotenv()
HF_TOKEN = os.getenv('HF_TOKEN')
DEFAULT_MODEL_SIZE = os.getenv('DEFAULT_MODEL_SIZE')
DEFAULT_COMPUTE_TYPE = os.getenv('DEFAULT_COMPUTE_TYPE')
DEFAULT_DEVICE = os.getenv('DEFAULT_DEVICE')


@dataclass
class Message:
    """Структура одного сообщения в диалоге"""
    role: str
    text: str


@dataclass
class DialogResult:
    """Структура результата обработки одного диалога"""
    id: Union[str, int]
    messages: List[Message]
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует в словарь для JSON"""
        return {
            "id": self.id,
            "messages": [{"role": m.role, "text": m.text} for m in self.messages]
        }
    
    def to_json(self) -> str:
        """Конвертирует в JSON строку"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def get_output_path(audio_path: str, 
                    output_dir: Optional[str] = None,
                    with_diarization: bool = False,
                    custom_name: Optional[str] = None) -> Optional[str]:
    """
    Генерирует путь для сохранения JSON результата.
    
    Args:
        audio_path: путь к аудиофайлу
        output_dir: директория для сохранения
        with_diarization: флаг диаризации (для имени файла)
        custom_name: пользовательское имя файла (без расширения)
        
    Returns:
        Путь для сохранения JSON файла или None
    """
    if output_dir is None:
        return None
    
    os.makedirs(output_dir, exist_ok=True)
    
    if custom_name:
        base_name = custom_name
    else:
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
    
    suffix = "_diarized" if with_diarization else ""
    json_path = os.path.join(output_dir, f"{base_name}{suffix}.json")
    
    return json_path


def save_result(result_obj: DialogResult, json_path: Optional[str] = None) -> None:
    """
    Сохраняет результат в JSON файл.
    
    Args:
        result_obj: объект результата
        json_path: путь для JSON файла
    """
    if json_path:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result_obj.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"✅ JSON сохранен: {json_path}")


def transcribe(audio_path: str, 
               dialog_id: Union[str, int] = None,
               model_size: str = DEFAULT_MODEL_SIZE,
               device: str = DEFAULT_DEVICE,
               compute_type: str = DEFAULT_COMPUTE_TYPE,
               output_dir: Optional[str] = None,
               custom_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Только транскрибация.
    
    Args:
        audio_path: путь к аудиофайлу
        dialog_id: идентификатор диалога
        model_size: размер модели
        device: устройство
        compute_type: тип вычислений
        output_dir: директория для сохранения результатов
        custom_name: пользовательское имя файла
        
    Returns:
        Словарь с результатом
    """
    if dialog_id is None:
        dialog_id = os.path.splitext(os.path.basename(audio_path))[0]
    
    json_path = get_output_path(audio_path, output_dir, False, custom_name)
    
    print("\n" + "="*80)
    print(f"ТРАНСКРИБАЦИЯ")
    print(f"Файл: {audio_path}, ID: {dialog_id}")
    if json_path:
        print(f"Сохранение: {json_path}")
    print("="*80)
    
    start_total = time.time()
    
    print("\n📁 Загрузка аудио...")
    audio = whisperx.load_audio(audio_path)
    audio_duration = len(audio) / 16000
    print(f"   Длительность: {audio_duration:.2f} сек")
    
    print("\n🎤 Транскрибация...")
    model = whisperx.load_model(model_size, device=device, compute_type=compute_type)
    
    transcribe_start = time.time()
    result = model.transcribe(audio)
    transcribe_time = time.time() - transcribe_start
    
    print(f"   ✅ Завершено за {transcribe_time:.2f} сек")
    print(f"   🗣️ Язык: {result['language']}")
    print(f"   📊 Сегментов: {len(result['segments'])}")
    
    del model
    gc.collect()
    
    messages = [Message(role="UNKNOWN", text=segment['text'].strip()) 
                for segment in result["segments"]]
    result_obj = DialogResult(id=dialog_id, messages=messages)
    result_dict = result_obj.to_dict()
    
    if json_path:
        save_result(result_obj, json_path)
    
    print(f"\n✅ ТРАНСКРИБАЦИЯ ЗАВЕРШЕНА за {time.time() - start_total:.2f} сек")
    print(f"📝 Всего реплик: {len(messages)}")
    
    return result_dict


def transcribe_with_diarization(audio_path: str,
                                dialog_id: Union[str, int] = None,
                                model_size: str = DEFAULT_MODEL_SIZE,
                                device: str = DEFAULT_DEVICE,
                                compute_type: str = DEFAULT_COMPUTE_TYPE,
                                hf_token: str = HF_TOKEN,
                                output_dir: Optional[str] = None,
                                custom_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Транскрибация с диаризацией.
    
    Args:
        audio_path: путь к аудиофайлу
        dialog_id: идентификатор диалога
        model_size: размер модели
        device: устройство
        compute_type: тип вычислений
        hf_token: токен Hugging Face
        output_dir: директория для сохранения результатов
        custom_name: пользовательское имя файла
        
    Returns:
        Словарь с результатом
    """
    if dialog_id is None:
        dialog_id = os.path.splitext(os.path.basename(audio_path))[0]
    
    json_path = get_output_path(audio_path, output_dir, True, custom_name)
    
    print("\n" + "="*80)
    print(f"ТРАНСКРИБАЦИЯ С ДИАРИЗАЦИЕЙ")
    print(f"Файл: {audio_path}, ID: {dialog_id}")
    if json_path:
        print(f"Сохранение: {json_path}")
    print("="*80)
    
    start_total = time.time()
    
    print("\n📁 Загрузка аудио...")
    audio = whisperx.load_audio(audio_path)
    audio_duration = len(audio) / 16000
    print(f"   Длительность: {audio_duration:.2f} сек")
    
    print("\n🎤 Транскрибация...")
    model = whisperx.load_model(model_size, device=device, compute_type=compute_type)
    
    transcribe_start = time.time()
    result = model.transcribe(audio)
    transcribe_time = time.time() - transcribe_start
    
    print(f"   ✅ Завершено за {transcribe_time:.2f} сек")
    print(f"   🗣️ Язык: {result['language']}")
    print(f"   📊 Сегментов: {len(result['segments'])}")
    
    del model
    gc.collect()
    
    print("\n⏱️ Выравнивание...")
    align_start = time.time()
    model_a, metadata = whisperx.load_align_model(
        language_code=result["language"],
        device=device
    )
    
    result_aligned = whisperx.align(
        result["segments"],
        model_a,
        metadata,
        audio,
        device=device,
        return_char_alignments=False
    )
    print(f"   ✅ Завершено за {time.time() - align_start:.2f} сек")
    
    del model_a
    gc.collect()
    
    print("\n👥 Диаризация...")
    diarize_start = time.time()
    
    diarize_model = whisperx.diarize.DiarizationPipeline(
        token=hf_token,
        device=device
    )
    
    diarize_segments = diarize_model(audio)
    speakers = diarize_segments['speaker'].unique()
    print(f"   ✅ Завершено за {time.time() - diarize_start:.2f} сек")
    print(f"   👥 Найдено спикеров: {len(speakers)}")
    
    for speaker in speakers:
        speaker_segments = diarize_segments[diarize_segments['speaker'] == speaker]
        total_time = (speaker_segments['end'] - speaker_segments['start']).sum()
        print(f"      {speaker}: {total_time:.1f} сек речи")
    
    result_with_speakers = whisperx.assign_word_speakers(diarize_segments, result_aligned)
    
    messages = []
    current_speaker = None
    current_text = []
    
    for segment in result_with_speakers["segments"]:
        speaker = segment.get('speaker', 'UNKNOWN')
        text = segment['text'].strip()
        
        if speaker == current_speaker:
            current_text.append(text)
        else:
            if current_speaker is not None and current_text:
                messages.append(Message(
                    role=current_speaker,
                    text=" ".join(current_text)
                ))
            current_speaker = speaker
            current_text = [text]
    
    if current_speaker is not None and current_text:
        messages.append(Message(
            role=current_speaker,
            text=" ".join(current_text)
        ))
    
    result_obj = DialogResult(id=dialog_id, messages=messages)
    result_dict = result_obj.to_dict()
    
    if json_path:
        save_result(result_obj, json_path)
    
    print("\n" + "="*80)
    print(f"✅ ЗАВЕРШЕНО за {time.time() - start_total:.2f} сек")
    print(f"📝 Всего реплик: {len(messages)}")
    print("="*80)
    
    return result_dict


def process_multiple_files(audio_files: List[str],
                           dialog_ids: Optional[List[Union[str, int]]] = None,
                           with_diarization: bool = False,
                           output_dir: Optional[str] = None,
                           **kwargs) -> List[Dict[str, Any]]:
    """
    Обрабатывает несколько аудиофайлов.
    
    Args:
        audio_files: список путей к аудиофайлам
        dialog_ids: список идентификаторов
        with_diarization: использовать ли диаризацию
        output_dir: директория для сохранения результатов
        **kwargs: параметры для функций транскрибации
        
    Returns:
        Список словарей с результатами
    """
    if dialog_ids is None:
        dialog_ids = [None] * len(audio_files)
    elif len(dialog_ids) != len(audio_files):
        raise ValueError("Количество dialog_ids должно совпадать с количеством audio_files")
    
    results = []
    func = transcribe_with_diarization if with_diarization else transcribe
    
    for i, (audio_path, dlg_id) in enumerate(zip(audio_files, dialog_ids)):
        print(f"\n{'='*80}")
        print(f"ФАЙЛ {i+1} ИЗ {len(audio_files)}")
        print(f"{'='*80}")
        
        result = func(audio_path, dlg_id, output_dir=output_dir, **kwargs)
        results.append(result)
    
    return results