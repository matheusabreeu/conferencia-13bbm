from http.server import BaseHTTPRequestHandler
import json
import gspread
from google.oauth2.service_account import Credentials
import os
from urllib.parse import urlparse, parse_qs

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

        # Descobre qual viatura o celular clicou (ex: ?vtr=ABT-34)
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        id_viatura = query_params.get('vtr', [''])[0]

        try:
            credenciais_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
            creds = Credentials.from_service_account_info(credenciais_json, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            cliente = gspread.authorize(creds)
            planilha = cliente.open_by_key('1vk2ZFjIYTGt8wPfXz3GBq6UzW_OkqEWrgwd8Sxn4r10')

            aba_catalogo = planilha.worksheet('Catalogo_Materiais')
            todos_materiais = aba_catalogo.get_all_records()
            
            # Filtra apenas os materiais da viatura clicada
            materiais = [m for m in todos_materiais if str(m.get('viatura_padrao', '')) == str(id_viatura)]

            # Puxa as viaturas e categorias para o caso do militar mover um material de lugar
            viaturas_bd = planilha.worksheet('Viaturas').get_all_records()
            lista_vtrs = [v['id_viatura'] for v in viaturas_bd if str(v.get('nome_viatura', '')).lower() != 'almoxarifado']
            
            lista_cats = []
            for v in viaturas_bd:
                if 'categoria' in v:
                    lista_cats.extend([c.strip() for c in str(v.get('categoria', '')).split(',') if c.strip()])
            lista_cats = sorted(list(set(lista_cats)))

            # Lê o histórico para mostrar o último status do material
            aba_registro = planilha.worksheet('Registro_Diario')
            registros = aba_registro.get_all_records()
            
            aba_militares = planilha.worksheet('Militares')
            dict_mils = {str(m['matricula']): m['nome_formatado'] for m in aba_militares.get_all_records()}
            
            historico = {str(r['id_material']): r for r in registros if str(r.get('id_viatura', '')) == str(id_viatura)}

            for mat in materiais:
                last = historico.get(str(mat['id_material']), {})
                mat['status_anterior'] = last.get('status_encontrado', 'Operante')
                mat['obs_anterior'] = last.get('observacao', '')
                mat['militar_anterior'] = dict_mils.get(str(last.get('matricula_conferente', '')), 'N/A')

            resposta = {
                "sucesso": True, 
                "materiais": materiais, 
                "vtrs": lista_vtrs, 
                "categorias": lista_cats
            }
        except Exception as e:
            resposta = {"sucesso": False, "mensagem": f"Erro no servidor: {str(e)}"}

        self.wfile.write(json.dumps(resposta).encode('utf-8'))
