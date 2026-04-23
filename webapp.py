from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
import os
import uuid
from pathlib import Path
from typing import Dict, Any
from whisperx_processor import transcribe, transcribe_with_diarization
import json

app = Flask(__name__)


app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['OUTPUT_FOLDER'] = './outputs'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Разрешенные расширения
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'flac', 'ogg', 'mp4', 'webm'}


def allowed_file(filename: str) -> bool:
    """Проверка разрешенного расширения файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# HTML шаблон для веб-интерфейса (минимальный)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>WhisperX Транскрибация</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 600px; margin: auto; }
        input, select, button { margin: 10px 0; padding: 8px; }
        .result { margin-top: 20px; padding: 15px; background: #f0f0f0; border-radius: 5px; }
        pre { white-space: pre-wrap; word-wrap: break-word; }
    </style>
</head>
<body>
    <div class="container">
        <h1>WhisperX Транскрибация</h1>
        <form method="post" enctype="multipart/form-data" action="/upload">
            <div>
                <label>Аудио файл:</label><br>
                <input type="file" name="audio" accept=".mp3,.wav,.m4a,.flac,.ogg" required>
            </div>
            <div>
                <label>Опции:</label><br>
                <input type="checkbox" name="with_diarization" value="true">
                <label>Использовать диаризацию (определение спикеров)</label>
            </div>
            <div>
                <label>ID диалога (опционально):</label><br>
                <input type="text" name="dialog_id" placeholder="Авто-генерация">
            </div>
            <button type="submit">Транскрибировать</button>
        </form>
        
        {% if result %}
        <div class="result">
            <h3>Результат:</h3>
            <pre>{{ result | safe }}</pre>
            {% if json_path %}
            <p><strong>Сохранено:</strong> {{ json_path }}</p>
            {% endif %}
        </div>
        {% endif %}
        
        {% if error %}
        <div class="result" style="background: #ffebee;">
            <h3>Ошибка:</h3>
            <p>{{ error }}</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
'''


@app.route('/')
def index():
    """Главная страница с формой загрузки"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/upload', methods=['POST'])
@app.route('/upload', methods=['POST'])
def upload_and_transcribe():    
    if 'audio' not in request.files:
        return render_template_string(
            HTML_TEMPLATE, 
            error="Файл не найден"
        )
    
    file = request.files['audio']
    
    if file.filename == '':
        return render_template_string(
            HTML_TEMPLATE, 
            error="Файл не выбран"
        )
    
    if not allowed_file(file.filename):
        return render_template_string(
            HTML_TEMPLATE, 
            error=f"Неподдерживаемый формат. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    try:
        original_filename = secure_filename(file.filename)
        unique_id = str(uuid.uuid4())[:4]
        filename = f"{unique_id}_{original_filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        with_diarization = request.form.get('with_diarization') == 'true'
        dialog_id = request.form.get('dialog_id')
        
        if not dialog_id:
            dialog_id = Path(original_filename).stem
        
        if with_diarization:
            result = transcribe_with_diarization(
                audio_path=filepath,
                dialog_id=dialog_id,
                output_dir=app.config['OUTPUT_FOLDER']
            )
        else:
            result = transcribe(
                audio_path=filepath,
                dialog_id=dialog_id,
                output_dir=app.config['OUTPUT_FOLDER']
            )
                
        suffix = "_diarized" if with_diarization else ""
        json_path = os.path.join(
            app.config['OUTPUT_FOLDER'], 
            f"{dialog_id}{suffix}.json"
        )
        
        # 👇 КОНВЕРТАЦИЯ В JSON С РУССКИМИ СИМВОЛАМИ
        result_json = json.dumps(result, ensure_ascii=False, indent=2)
        
        return render_template_string(
            HTML_TEMPLATE,
            result=result_json,  # 👈 ПЕРЕДАЕМ JSON СТРОКУ
            json_path=json_path if os.path.exists(json_path) else None
        )
        
    except Exception as e:
        return render_template_string(
            HTML_TEMPLATE,
            error=f"Ошибка при обработке: {str(e)}"
        )

@app.route('/api/transcribe', methods=['POST'])
def api_transcribe():
    """
    API эндпоинт для транскрибации
    Возвращает JSON результат
    """
    if 'audio' not in request.files:
        return jsonify({"error": "Audio file required"}), 400
    
    file = request.files['audio']
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": f"Format not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
    
    try:
        original_filename = secure_filename(file.filename)
        unique_id = str(uuid.uuid4())[:4]
        filename = f"{unique_id}_{original_filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
                
        with_diarization = request.args.get('with_diarization', 'false').lower() == 'true'
        dialog_id = request.args.get('dialog_id')
        
        if not dialog_id:
            dialog_id = Path(original_filename).stem
        
        # Транскрибация
        if with_diarization:
            result = transcribe_with_diarization(
                audio_path=filepath,
                dialog_id=dialog_id,
                output_dir=app.config['OUTPUT_FOLDER']
            )
        else:
            result = transcribe(
                audio_path=filepath,
                dialog_id=dialog_id,
                output_dir=app.config['OUTPUT_FOLDER']
            )
        
        os.remove(filepath)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка работоспособности сервера"""
    return jsonify({
        "status": "healthy",
        "upload_folder": app.config['UPLOAD_FOLDER'],
        "output_folder": app.config['OUTPUT_FOLDER']
    })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Запуск Flask сервера")
    print("="*60)
    print(f"📁 Загрузки: {app.config['UPLOAD_FOLDER']}")
    print(f"📁 Результаты: {app.config['OUTPUT_FOLDER']}")
    print("   - http://localhost:5000/           → Веб-интерфейс")
    print("\n✨ Сервер запущен...")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)