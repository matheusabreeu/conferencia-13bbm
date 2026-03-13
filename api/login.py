from http.server import BaseHTTPRequestHandler
import json
import gspread
from google.oauth2.service_account import Credentials
import os

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        dados = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8'))
        matricula_digitada = str(dados.get('matricula')).strip()

        try:
            credenciais_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
            creds = Credentials.from_service_account_info(credenciais_json, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            cliente = gspread.authorize(creds)
            aba_militares = cliente.open_by_key('1vk2ZFjIYTGt8wPfXz3GBq6UzW_OkqEWrgwd8Sxn4r10').worksheet('Militares')
            registros = aba_militares.get_all_records()

            militar_encontrado = None
            lista_militares = []
            
            for militar in registros:
                status = str(militar.get('status', '')).strip().lower()
                matricula = str(militar.get('matricula', '')).strip()
                
                if matricula != '' and status != 'inativo':
                    lista_militares.append({
                        "nome_guerra": str(militar.get('nome_formatado', '')),
                        "nome_completo": str(militar.get('nome_completo', '')),
                        "matricula": matricula
                    })
                    
                if matricula == matricula_digitada:
                    militar_encontrado = militar

            if not militar_encontrado:
                resposta = {"sucesso": False, "mensagem": "Matrícula não encontrada."}
            elif str(militar_encontrado.get('status', '')).strip().lower() == 'inativo':
                resposta = {"sucesso": False, "mensagem": "Militar inativo."}
            else:
                resposta = {
                    "sucesso": True,
                    "nome_guerra": militar_encontrado.get('nome_formatado', ''),
                    "nivel_acesso": str(militar_encontrado.get('nivel_acesso', '')).strip().lower(),
                    "matricula": matricula_digitada,
                    "militares": lista_militares
                }
        except Exception as e:
            resposta = {"sucesso": False, "mensagem": f"Erro no servidor."}

        self.wfile.write(json.dumps(resposta).encode('utf-8'))
