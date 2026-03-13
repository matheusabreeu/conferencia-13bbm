from http.server import BaseHTTPRequestHandler
import json
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime, timezone, timedelta

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
            # Recebe o pacotão de dados que o celular enviou
            dados = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8'))
            id_viatura = dados.get('id_viatura')
            matricula = dados.get('matricula')
            materiais_conferidos = dados.get('materiais', [])

            credenciais_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
            # Atenção: Permissão para ESCREVER na planilha (sem o .readonly)
            creds = Credentials.from_service_account_info(credenciais_json, scopes=['https://www.googleapis.com/auth/spreadsheets'])
            cliente = gspread.authorize(creds)
            planilha = cliente.open_by_key('1vk2ZFjIYTGt8wPfXz3GBq6UzW_OkqEWrgwd8Sxn4r10')

            aba_registro = planilha.worksheet('Registro_Diario')
            aba_catalogo = planilha.worksheet('Catalogo_Materiais')
            cat_records = aba_catalogo.get_all_records()

            fuso_br = timezone(timedelta(hours=-3))
            agora = datetime.now(fuso_br).strftime('%d/%m/%Y %H:%M:%S')

            # Função para criar um novo ID (ex: M104) se o militar dividir um lote
            def gerar_novo_id(lista_cats):
                max_num = 0
                for mat in lista_cats:
                    try:
                        num = int(str(mat['id_material']).upper().replace('M', ''))
                        if num > max_num: max_num = num
                    except: pass
                return f"M{max_num + 1:03d}"

            linhas_registro = []

            for item in materiais_conferidos:
                m_id = item.get('id_material')
                status = item.get('status')
                obs = item.get('obs', '')
                comp_atual = item.get('comp', '')
                qtd_informada = int(item.get('qtde', 0))
                
                nova_vtr = id_viatura
                mat_orig = next((m for m in cat_records if str(m['id_material']) == str(m_id)), None)

                # LÓGICA DE MOVIMENTAÇÃO DE MATERIAL
                if status == 'Movido' and mat_orig:
                    nova_vtr = item.get('nova_vtr')
                    novo_comp = item.get('novo_comp')
                    qtd_padrao = int(mat_orig['quantidade_padrao'])
                    
                    obs = f"Movido para {nova_vtr} ({novo_comp}). Motivo: {obs}"
                    comp_atual = novo_comp
                    
                    # Se ele moveu apenas uma parte (ex: 1 de 3 mangueiras)
                    if qtd_informada < qtd_padrao:
                        nova_qtd_orig = qtd_padrao - qtd_informada
                        cel_orig = aba_catalogo.find(m_id)
                        if cel_orig: 
                            aba_catalogo.update_cell(cel_orig.row, 5, nova_qtd_orig) # Subtrai do original
                        
                        novo_id = gerar_novo_id(cat_records)
                        # Cria o novo item na nova viatura
                        aba_catalogo.append_row([novo_id, mat_orig['nome_material'], nova_vtr, novo_comp, qtd_informada])
                        cat_records.append({'id_material': novo_id, 'nome_material': mat_orig['nome_material'], 'viatura_padrao': nova_vtr, 'categoria': novo_comp, 'quantidade_padrao': qtd_informada})
                        
                        # Registra os dois fatos no diário
                        linhas_registro.append([agora, matricula, nova_vtr, novo_id, 'Movido', novo_comp, qtd_informada, obs])
                        linhas_registro.append([agora, matricula, id_viatura, m_id, 'Operante', mat_orig['categoria'], nova_qtd_orig, 'Restante da Divisao de Lote'])
                        continue 
                    
                    # Se ele moveu TUDO, só altera a localização original
                    else:
                        try:
                            celula = aba_catalogo.find(m_id)
                            if celula:
                                aba_catalogo.update_cell(celula.row, 3, nova_vtr) # Coluna viatura
                                aba_catalogo.update_cell(celula.row, 4, novo_comp) # Coluna categoria
                        except: pass

                # Grava o status no diário (Operante, Avariado, Extraviado, Inoperante, ou o Movido total)
                linhas_registro.append([agora, matricula, nova_vtr, m_id, status, comp_atual, qtd_informada, obs])

            # Despeja tudo de uma vez no banco de dados para ser muito rápido
            if linhas_registro: 
                aba_registro.append_rows(linhas_registro)

            resposta = {"sucesso": True, "mensagem": "Conferência salva com sucesso!"}
        except Exception as e:
            resposta = {"sucesso": False, "mensagem": f"Erro no servidor: {str(e)}"}

        self.wfile.write(json.dumps(resposta).encode('utf-8'))
