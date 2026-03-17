from whisperx_processor import transcribe, transcribe_with_diarization, process_multiple_files

def main():
   # 1. Просто транскрибация в TXT
    res1 = transcribe(
        audio_path="C:\\Users\\user\\Desktop\\ASR\\project_whisperX\\Voice\\example.wav",
        output_dir="./results"
    )

    # 2. С диаризацией (автоматически сохраняет в JSON если нужно)
    res2 = transcribe_with_diarization(
        audio_path="C:\\Users\\user\\Desktop\\ASR\\project_whisperX\\Voice\\example.wav",
        output_dir="./results",
        custom_name="my_name"
    )

    # 3. Несколько файлов
    res3 = process_multiple_files(
        audio_files=["C:\\Users\\user\\Desktop\\ASR\\project_whisperX\\Voice\\example.wav", "C:\\Users\\user\\Desktop\\ASR\\project_whisperX\\Voice\\1.wav"],
        with_diarization=True,  # или False для простой транскрибации
        output_dir="./results"
    )
if __name__ == "__main__":
    main()