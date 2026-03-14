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
            planilha = cliente.open_by_key('1vk2ZFjIYTGt8wPfXz3GBq6UzW_OkqEWrgwd8Sxn4r10')
            
            aba_viaturas = planilha.worksheet('Viaturas')
            registros_vtr = aba_viaturas.get_all_records()

            lista_viaturas = []
            for v in registros_vtr:
                if str(v.get('nome_viatura', '')).strip().lower() != 'almoxarifado':
                    lista_viaturas.append({
                        "id_viatura": str(v.get('id_viatura', '')),
                        "nome_viatura": str(v.get('nome_viatura', '')),
                        "categoria": str(v.get('categoria', ''))
                    })

            # PUXAR O HISTÓRICO
            aba_registro = planilha.worksheet('Registro_Diario').get_all_records()
            aba_militares = planilha.worksheet('Militares').get_all_records()
            dict_mils = {str(m['matricula']): str(m.get('nome_formatado', '')) for m in aba_militares if 'matricula' in m}
            
            historico = []
            vistos = set()
            for r in reversed(aba_registro):
                dh = str(r.get('data_hora', ''))
                mat = str(r.get('matricula_conferente', ''))
                if not dh: continue
                chave = f"{dh[:16]}_{mat}" # Agrupa por minuto para não repetir
                
                if chave not in vistos:
                    vistos.add(chave)
                    historico.append({"data": dh, "militar": dict_mils.get(mat, "Desconhecido")})
                    if len(historico) == 4: break

            resposta = {"sucesso": True, "viaturas": lista_viaturas, "historico": historico}
        except Exception as e:
            resposta = {"sucesso": False, "mensagem": f"Erro no servidor: {str(e)}"}

        self.wfile.write(json.dumps(resposta).encode('utf-8'))
