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

        try:
            dados = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8'))
            termo_busca = str(dados.get('termo', '')).strip().lower()

            credenciais_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
            creds = Credentials.from_service_account_info(credenciais_json, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            cliente = gspread.authorize(creds)
            planilha = cliente.open_by_key('1vk2ZFjIYTGt8wPfXz3GBq6UzW_OkqEWrgwd8Sxn4r10')

            cat_materiais = planilha.worksheet('Catalogo_Materiais').get_all_records()
            registros = planilha.worksheet('Registro_Diario').get_all_records()
            militares = planilha.worksheet('Militares').get_all_records()

            dict_mils = {str(m['matricula']): str(m.get('nome_formatado', '')) for m in militares}
            
            # Agrupa o histórico para sabermos qual foi o último registo de cada material
            ultimos_registros = {str(r['id_material']): r for r in registros}

            resultados = []
            for mat in cat_materiais:
                nome = str(mat.get('nome_material', '')).lower()
                id_mat = str(mat.get('id_material', '')).lower()
                
                # Se o texto pesquisado estiver no nome ou no ID, adiciona aos resultados
                if termo_busca in nome or termo_busca in id_mat:
                    r_recente = ultimos_registros.get(str(mat['id_material']), {})
                    
                    resultados.append({
                        "id_material": str(mat['id_material']),
                        "nome_material": str(mat['nome_material']),
                        "viatura_padrao": str(mat.get('viatura_padrao', '')),
                        "categoria_padrao": str(mat.get('categoria', '')),
                        "local_visto": str(r_recente.get('id_viatura', mat.get('viatura_padrao', ''))),
                        "status_atual": str(r_recente.get('status_encontrado', 'Operante (Padrão)')),
                        "obs": str(r_recente.get('observacao', '')),
                        "data_visto": str(r_recente.get('data_hora', 'Sem registo recente')),
                        "quem_viu": dict_mils.get(str(r_recente.get('matricula_conferente', '')), 'N/A')
                    })

            resposta = {"sucesso": True, "resultados": resultados}
        except Exception as e:
            resposta = {"sucesso": False, "mensagem": f"Erro no servidor: {str(e)}"}

        self.wfile.write(json.dumps(resposta).encode('utf-8'))
