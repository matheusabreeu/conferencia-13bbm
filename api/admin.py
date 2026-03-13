from http.server import BaseHTTPRequestHandler
import json
import gspread
from google.oauth2.service_account import Credentials
import os

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        # Carrega os dados para abrir o painel
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        try:
            credenciais_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
            creds = Credentials.from_service_account_info(credenciais_json, scopes=['https://www.googleapis.com/auth/spreadsheets'])
            cliente = gspread.authorize(creds)
            planilha = cliente.open_by_key('1vk2ZFjIYTGt8wPfXz3GBq6UzW_OkqEWrgwd8Sxn4r10')
            
            materiais = planilha.worksheet('Catalogo_Materiais').get_all_records()
            viaturas_bd = planilha.worksheet('Viaturas').get_all_records()
            
            lista_viaturas = [v['id_viatura'] for v in viaturas_bd if str(v.get('nome_viatura', '')).lower() != 'almoxarifado']
            lista_cats = []
            for v in viaturas_bd:
                if 'categoria' in v:
                    lista_cats.extend([c.strip() for c in str(v.get('categoria', '')).split(',') if c.strip()])
            lista_cats = sorted(list(set(lista_cats)))
            
            # Descobre qual o próximo ID (ex: M105)
            max_num = 0
            for m in materiais:
                try:
                    num = int(str(m['id_material']).upper().replace('M', ''))
                    if num > max_num: max_num = num
                except: pass
            prox_id = f"M{max_num + 1:03d}"
            
            resposta = {"sucesso": True, "materiais": materiais, "viaturas": lista_viaturas, "categorias": lista_cats, "prox_id": prox_id}
        except Exception as e:
            resposta = {"sucesso": False, "mensagem": str(e)}
        
        self.wfile.write(json.dumps(resposta).encode('utf-8'))

    def do_POST(self):
        # Recebe a ordem de Adicionar ou Remover
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        try:
            dados = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8'))
            acao = dados.get('acao')
            
            credenciais_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
            creds = Credentials.from_service_account_info(credenciais_json, scopes=['https://www.googleapis.com/auth/spreadsheets'])
            cliente = gspread.authorize(creds)
            aba = cliente.open_by_key('1vk2ZFjIYTGt8wPfXz3GBq6UzW_OkqEWrgwd8Sxn4r10').worksheet('Catalogo_Materiais')
            
            if acao == 'adicionar':
                aba.append_row([dados.get('id'), dados.get('nome'), dados.get('viatura'), dados.get('categoria'), dados.get('qtde')])
                resposta = {"sucesso": True, "mensagem": "Material adicionado com sucesso!"}
            elif acao == 'remover':
                celula = aba.find(dados.get('id'))
                if celula:
                    aba.delete_rows(celula.row)
                    resposta = {"sucesso": True, "mensagem": "Material excluído do batalhão!"}
                else:
                    resposta = {"sucesso": False, "mensagem": "ID não encontrado."}
            else:
                resposta = {"sucesso": False, "mensagem": "Ação inválida."}
        except Exception as e:
            resposta = {"sucesso": False, "mensagem": str(e)}
            
        self.wfile.write(json.dumps(resposta).encode('utf-8'))
