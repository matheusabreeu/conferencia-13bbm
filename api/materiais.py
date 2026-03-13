from http.server import BaseHTTPRequestHandler
import json
import gspread
from google.oauth2.service_account import Credentials
import os
from urllib.parse import urlparse, parse_qs

# NOVA FUNÇÃO DE BLINDAGEM E RAIO-X
def ler_aba_segura(planilha, nome_aba):
    try:
        aba = planilha.worksheet(nome_aba)
        valores = aba.get_all_values()
        if not valores:
            return [] # Se o robô vir a aba vazia, não trava, apenas devolve vazio
        return aba.get_all_records()
    except Exception as e:
        raise Exception(f"Falha ao ler a aba '{nome_aba}': {str(e)}")

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

        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        id_viatura = query_params.get('vtr', [''])[0]

        try:
            credenciais_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
            creds = Credentials.from_service_account_info(credenciais_json, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            cliente = gspread.authorize(creds)
            planilha = cliente.open_by_key('1vk2ZFjIYTGt8wPfXz3GBq6UzW_OkqEWrgwd8Sxn4r10')

            # Leituras usando a nova função blindada
            todos_materiais = ler_aba_segura(planilha, 'Catalogo_Materiais')
            viaturas_bd = ler_aba_segura(planilha, 'Viaturas')
            registros = ler_aba_segura(planilha, 'Registro_Diario')
            militares_bd = ler_aba_segura(planilha, 'Militares')

            materiais = [m for m in todos_materiais if str(m.get('viatura_padrao', '')) == str(id_viatura)]

            lista_vtrs = [v['id_viatura'] for v in viaturas_bd if str(v.get('nome_viatura', '')).lower() != 'almoxarifado' and 'id_viatura' in v]
            
            lista_cats = []
            for v in viaturas_bd:
                if 'categoria' in v:
                    lista_cats.extend([c.strip() for c in str(v.get('categoria', '')).split(',') if c.strip()])
            lista_cats = sorted(list(set(lista_cats)))

            dict_mils = {str(m['matricula']): m.get('nome_formatado', '') for m in militares_bd if 'matricula' in m}
            
            historico = {str(r['id_material']): r for r in registros if str(r.get('id_viatura', '')) == str(id_viatura)}

            for mat in materiais:
                last = historico.get(str(mat.get('id_material', '')), {})
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
            resposta = {"sucesso": False, "mensagem": str(e)}

        self.wfile.write(json.dumps(resposta).encode('utf-8'))
