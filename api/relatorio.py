from http.server import BaseHTTPRequestHandler
import json
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime, timezone, timedelta
import urllib.parse

# NOVA FUNÇÃO DE BLINDAGEM E RAIO-X
def ler_aba_segura(planilha, nome_aba):
    try:
        aba = planilha.worksheet(nome_aba)
        valores = aba.get_all_values()
        if not valores:
            return []
        return aba.get_all_records()
    except Exception as e:
        raise Exception(f"Falha ao ler a aba '{nome_aba}': {str(e)}")

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
            guarnicao = dados.get('guarnicao', [])

            credenciais_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
            creds = Credentials.from_service_account_info(credenciais_json, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            cliente = gspread.authorize(creds)
            planilha = cliente.open_by_key('1vk2ZFjIYTGt8wPfXz3GBq6UzW_OkqEWrgwd8Sxn4r10')

            registros = ler_aba_segura(planilha, 'Registro_Diario')
            catalogo = ler_aba_segura(planilha, 'Catalogo_Materiais')
            militares = ler_aba_segura(planilha, 'Militares')

            t_socorro = ""
            try:
                config_dados = ler_aba_segura(planilha, 'Configuracoes')
                confs = {str(c.get('cargo')).strip(): str(c.get('telefone_whatsapp')).strip() for c in config_dados if 'cargo' in c}
                t_socorro = confs.get('chefe_socorro', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            except: pass

            lista_contatos = [{'nome': m.get('nome_formatado', ''), 'tel': str(m.get('telefone', '')).replace(' ', '').replace('-', '').replace('(', '').replace(')', '')} for m in militares if m.get('telefone')]
            dict_nomes_materiais = {str(m.get('id_material', '')).strip(): str(m.get('nome_material', '')).strip() for m in catalogo}
            
            fuso_br = timezone(timedelta(hours=-3))
            agora = datetime.now(fuso_br)
            hoje_str = agora.strftime('%d/%m/%Y')
            dias = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

            registros_hoje = [r for r in registros if hoje_str in str(r.get('data_hora', ''))]
            
            ultimos_hoje = {}
            for r in registros_hoje:
                ultimos_hoje[str(r.get('id_material', '')).strip()] = r

            vtrs_conferidas = set(str(r.get('id_viatura')) for r in registros_hoje)
            locais_obrigatorios = ['ABT-34', 'AR-75', 'Permanência']
            viaturas_pendentes = [loc for loc in locais_obrigatorios if loc not in vtrs_conferidas and loc.replace('ê','e') not in vtrs_conferidas]

            aviso_pendencia = f"Atenção: Você ainda não conferiu estes locais: {', '.join(viaturas_pendentes)}" if viaturas_pendentes else None

            agrupamento_vtrs = {}
            alteracoes = []

            for m_id, r in ultimos_hoje.items():
                if not m_id: continue
                nome_real = dict_nomes_materiais.get(m_id, m_id)
                local_vtr = str(r.get('id_viatura', 'LOCAL NAO INFORMADO')).strip()
                local_comp = str(r.get('compartimento_encontrado', '')).strip()
                texto_comp = f" ({local_comp})" if local_comp else ""
                qtd = r.get('qtde_encontrado', 0)
                status = r.get('status_encontrado', '')
                
                if status in ['Operante', 'Movido']:
                    if local_vtr not in agrupamento_vtrs: agrupamento_vtrs[local_vtr] = []
                    agrupamento_vtrs[local_vtr].append(f"{nome_real}{texto_comp} - Qtd: {qtd}")
                else:
                    alteracoes.append(f"[ALTERACAO] *{local_vtr}{texto_comp}* - {nome_real} | Status: {status} | Obs: _{r.get('observacao', '')}_")

            viaturas_ordenadas = sorted(agrupamento_vtrs.keys())

            texto = "*SECRETARIA DE SEGURANÇA PÚBLICA*\n*CORPO DE BOMBEIROS MILITAR DO MARANHÃO*\n*COMANDO OPERACIONAL METROPOLITANO*\n*13º BATALHÃO DE BOMBEIROS MILITAR*\n\n"
            texto += f"*Serviço Operacional do 13° BBM do dia {hoje_str} ({dias[agora.weekday()]})*\n\n"

            if not guarnicao:
                texto += "GUARNIÇÃO NÃO CADASTRADA (Gere a escala no site principal)\n\n"
            else:
                for militar in guarnicao:
                    texto += f"*{str(militar.get('funcao', '')).upper()}*\n_{militar.get('nome', '')}_\n\n"

            texto += "*VTRS:*\n_(Status geral das viaturas gerado automaticamente)_\n\n"
            texto += "*MATERIAIS E EQUIPAMENTOS:*\n\n"

            if viaturas_ordenadas:
                for vtr in viaturas_ordenadas:
                    texto += f"*{vtr}*\n"
                    for item in agrupamento_vtrs[vtr]:
                        texto += f"{item}\n"
                    texto += "\n"
            else:
                texto += "Nenhum material conferido no sistema hoje.\n\n"

            texto += "*ALTERAÇÕES GERAIS:*\n"
            if alteracoes:
                texto += "\n".join(alteracoes)
            else:
                texto += "Nenhuma alteração de material registrada. [OK]"

            resposta = {
                "sucesso": True,
                "texto": texto,
                "texto_codificado": urllib.parse.quote(texto),
                "t_socorro": t_socorro,
                "contatos": lista_contatos,
                "aviso": aviso_pendencia
            }
        except Exception as e:
            resposta = {"sucesso": False, "mensagem": str(e)}

        self.wfile.write(json.dumps(resposta).encode('utf-8'))
