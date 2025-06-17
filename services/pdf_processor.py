import pdfplumber

def extract_text_from_pdfs(filepath):
    text = ""
    try:
        print(f"Extraindo texto de {filepath}")
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                else:
                    print(f"Aviso: Página {page.page_number} sem texto extraível")
                    
        if not text.strip():
            print(f"Erro: Nenhum texto extraído de {filepath}")
            return None
            
    except Exception as e:
        print(f"Erro ao processar {filepath}: {str(e)}")
        return None
        
    return text.strip()
