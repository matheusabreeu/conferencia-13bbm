from http.server import BaseHTTPRequestHandler
import json
import gspread
from google.oauth2.service_account import Credentials
import os

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            credenciais_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
            creds = Credentials.from_service_account_info(credenciais_json, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            cliente = gspread.authorize(creds)
            
            # Puxa a aba Viaturas da sua planilha
            aba_viaturas = cliente.open_by_key('1vk2ZFjIYTGt8wPfXz3GBq6UzW_OkqEWrgwd8Sxn4r10').worksheet('Viaturas')
            registros = aba_viaturas.get_all_records()

            lista_viaturas = []
            for v in registros:
                # Remove o Almoxarifado da lista de viaturas
                if str(v.get('nome_viatura', '')).strip().lower() != 'almoxarifado':
                    lista_viaturas.append({
                        "id_viatura": str(v.get('id_viatura', '')),
                        "nome_viatura": str(v.get('nome_viatura', '')),
                        "categoria": str(v.get('categoria', '')) # Atualizado com a sua nova coluna
                    })

            resposta = {"sucesso": True, "viaturas": lista_viaturas}
        except Exception as e:
            resposta = {"sucesso": False, "mensagem": f"Erro no servidor: {str(e)}"}

        self.wfile.write(json.dumps(resposta).encode('utf-8'))
