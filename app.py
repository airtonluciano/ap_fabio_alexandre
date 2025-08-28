from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import pandas as pd
from dotenv import load_dotenv
import json
import time
import sys
import re

# Definir caminho base sem depender de __file__
BASE_DIR = os.getcwd()
SERVICES_DIR = os.path.join(BASE_DIR, 'services')
sys.path.append(SERVICES_DIR)

try:
    from pdf_processor import extract_text_from_pdfs
    from openrouter_service import extract_guests_data
    from excel_exporter import export_to_excel
except ModuleNotFoundError as e:
    raise ImportError("Erro ao importar módulos de services. Verifique se os arquivos estão no diretório correto.") from e

load_dotenv()

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def correct_reversed_text(text):
    """
    Corrige o texto extraído de PDFs onde algumas linhas podem estar invertidas
    devido à formatação vertical.
    """
    lines = text.split('\n')
    corrected_lines = []
    for line in lines:
        # Inverte linhas que parecem ser o número do requerimento ou a palavra "REQ" em inglês
        if re.search(r'\d{4}/\d+\.n', line) or 'QER' in line.upper():
            corrected_lines.append(line[::-1])
        else:
            corrected_lines.append(line)
    return '\n'.join(corrected_lines)

@app.route('/')
def index():
    with open('config/models.json') as f:
        models = json.load(f)
    return render_template('index.html', models=models)

@app.route('/upload', methods=['POST'])
def upload_files():
    files = request.files.getlist('files[]')
    filenames = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            filenames.append(filename)
    return jsonify({'uploaded': filenames})

@app.route('/process', methods=['POST'])
def process_files():
    data = request.json
    filenames = data.get('filenames')
    model = data.get('model')
    all_data = []
    for filename in filenames:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        text = extract_text_from_pdfs(filepath)
        if text is None:
            print(f"Erro: Falha na extração de texto de {filename}")
            continue

        # Corrige o texto antes de salvar e enviar para o modelo
        corrected_text = correct_reversed_text(text)

        # Salvar o texto corrigido em um arquivo .txt para depuração
        txt_filename = os.path.splitext(filename)[0] + '_corrigido.txt'
        txt_filepath = os.path.join(app.config['UPLOAD_FOLDER'], txt_filename)
        with open(txt_filepath, 'w', encoding='utf-8') as txt_file:
            txt_file.write(corrected_text)
            
        try:
            # Envia o texto corrigido para o modelo
            guests = extract_guests_data(corrected_text, model)
            if not guests:
                print(f"Aviso: Nenhum convidado extraído de {filename}")
                continue
            for guest in guests:
                guest['arquivo'] = filename
                all_data.append(guest)
        except Exception as e:
            print(f"Erro ao processar {filename}: {str(e)}")
            continue
    if not all_data:
        return jsonify({"error": "Nenhum dado extraído"}), 400
        
    # Manually serialize to handle potential datetime objects
    safe_data = []
    for item in all_data:
        safe_item = {k: str(v) if pd.notnull(v) else '' for k, v in item.items()}
        safe_data.append(safe_item)
    
    return jsonify({
        "data": safe_data,
        "columns": ["requerimento", "pronome", "nome", "cargo", "entidade", "observacoes", "autores"]
    })

@app.route('/export', methods=['POST'])
def export():
    data = request.get_json(force=True, silent=True)

    if not isinstance(data, list):
        return jsonify({"error": "Formato inválido: esperado uma lista de objetos JSON"}), 400

    column_order = ['requerimento', 'autores', 'pronome', 'nome', 'cargo', 'entidade', 'observacoes']
    df = pd.DataFrame(data, columns=column_order)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"convidados_{timestamp}.xlsx"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    export_to_excel(df, filepath)
    return send_file(filepath, as_attachment=True)

@app.route('/clear_uploaded_pdfs', methods=['POST'])
def clear_uploaded_pdfs():
    deleted_count = 0
    error_count = 0
    upload_folder = app.config['UPLOAD_FOLDER']

    if not os.path.exists(upload_folder):
        return jsonify({'message': 'Diretório de uploads não encontrado.', 'errors': True}), 404

    for filename in os.listdir(upload_folder):
        if filename.lower().endswith(('.pdf', '.xlsx', '.txt')):
            filepath = os.path.join(upload_folder, filename)
            try:
                os.remove(filepath)
                deleted_count += 1
            except Exception as e:
                print(f"Erro ao remover {filepath}: {e}")
                error_count += 1

    message = f"{deleted_count} arquivos PDF foram removidos."
    if error_count > 0:
        message += f" Ocorreram {error_count} erros ao tentar remover alguns arquivos."

    if deleted_count == 0 and error_count == 0:
        message = "Nenhum arquivo PDF encontrado para remover."

    return jsonify({'message': message, 'errors': error_count > 0})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
