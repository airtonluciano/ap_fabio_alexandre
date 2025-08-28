from openai import OpenAI
import os
from dotenv import load_dotenv
import json
import re

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

def extract_guests_data(pdf_text, model_name):
    if not pdf_text:
        print("Erro: Texto do PDF vazio ou inválido")
        return []

    try:
        print(f"Extraindo dados de convidados usando o modelo: {model_name}")
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": os.getenv("SITE_URL", "http://localhost:5000"),
                "X-Title": "Extrator de Convidados - Requerimentos",
            },
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": r"""Você é um assistente de inteligência artificial especializado em extrair dados de arquivos PDF.

                  Os arquivos que você recebe são referentes a requerimentos de audiências públicas no parlamento. Desses arquivos, você deve extrair uma relação de convidados para o debate proposto e se limitará a retornar os convidados explicitamente mencionados.

                  Para cada convidado, você vai tentar identificar:
                    - requerimento: Número do requerimento (ex: "REQ n.123/2024"). Se não encontrar, use "Não identificado".
                    - genero: Inferir quando possível ("M", "F" ou "Não identificado")
                    - pronome: Se não estiver especificado, usar "Sr." ou "Sra.", de acordo com o gênero, ou "Não identificado"
                    - nome: Se não houver nome explícito, use "Representante não especificado"
                    - cargo: Descrição do cargo ou qualificações
                    - entidade: Organização/instituição que representa
                    - observacoes: Contexto da menção no documento
                    - autores: Nome(s) do(s) deputado(s) autor(es) do requerimento. Se não houver nome explícito, use 'Não identificado(s)'.

                  IMPORTANTE:
                    - Mantenha cada entrada mesmo com dados parciais.
                    - O campo 'requerimento' e 'autores' devem ser os mesmos para todos os convidados de um mesmo arquivo processado.
                    - Retorne apenas um array JSON válido.
                    - Não escreva explicações, apenas o JSON.
                    - Use aspas duplas no JSON.

                  Exemplo esperado de saída JSON:

                  [
                    {
                      "requerimento": "REQ n.9/2025",
                      "autores": "Deputado João Pedra",
                      "pronome": "Sr.",
                      "genero": "M",
                      "nome": "José Silva",
                      "cargo": "Produtor rural",
                      "entidade": "Associação de Agricultores",
                      "observacoes": "Mencionado genericamente no contexto do debate"                      
                    },
                    {
                      "requerimento": "REQ n.9/2025",
                      "autores": "Deputado João Pedra",
                      "pronome": "Sr./Sra.",
                      "genero": "Não identificado",
                      "nome": "Representante não especificado",
                      "cargo": "Líder comunitário",
                      "entidade": "Comunidades tradicionais",
                      "observacoes": "Participação necessária para representação dos interesses locais"
                    }
                  ]
                  """
                },
                {
                    "role": "user",
                    "content": f"""
                        Extraia os dados dos números dos requerimentos, seus autores e os dados dos convidados desses requerimentos de audiência pública.
                        Texto do requerimento: {pdf_text}
                        """
                }
            ]
        )
        
        response = completion.choices[0].message.content
        #debug print(f"Resposta bruta do modelo: {response}")
        
        # Limpar a resposta removendo blocos de código markdown
        cleaned_response = clean_json_response(response)
        #debug print(f"Resposta limpa: {cleaned_response}")
        
        # Validar se o response é um JSON válido
        try:
            data = json.loads(cleaned_response)
            if not isinstance(data, list):
                print(f"Erro: Formato inválido de resposta - Não é uma lista")
                return []
            return data
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON: {str(e)}")
            print(f"Resposta que causou erro: {cleaned_response}")
            return []
            
    except Exception as e:
        print(f"Erro na chamada da API: {str(e)}")
        return []

def clean_json_response(response):
    """
    Função para limpar a resposta da API removendo blocos de código markdown
    e outros caracteres desnecessários.
    """
    if not response:
        return response
    
    # Remove blocos de código markdown (```json ... ``` ou ``` ... ```)
    response = re.sub(r'```json\s*', '', response)
    response = re.sub(r'```\s*', '', response)
    
    # Remove quebras de linha extras no início e fim
    response = response.strip()
    
    # Se a resposta começar com explicações antes do JSON, tenta extrair apenas o JSON
    # Procura pelo primeiro [ ou { e pelo último ] ou }
    json_start = -1
    json_end = -1
    
    # Procura pelo início do JSON
    for i, char in enumerate(response):
        if char in '[{':
            json_start = i
            break
    
    # Procura pelo fim do JSON (do final para o início)
    for i in range(len(response) - 1, -1, -1):
        if response[i] in ']}':
            json_end = i + 1
            break
    
    # Se encontrou tanto início quanto fim, extrai apenas essa parte
    if json_start != -1 and json_end != -1 and json_start < json_end:
        response = response[json_start:json_end]
    
    return response