from http.server import BaseHTTPRequestHandler
import json
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime, timezone, timedelta

def ler_aba_segura(planilha, nome_aba):
    aba = planilha.worksheet(nome_aba)
    valores = aba.get_all_values()
    if not valores or len(valores) <= 1: return []
    return aba.get_all_records()

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
            status_vtrs = dados.get('viaturas_status', {})

            credenciais_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
            creds = Credentials.from_service_account_info(credenciais_json, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            cliente = gspread.authorize(creds)
            planilha = cliente.open_by_key('1vk2ZFjIYTGt8wPfXz3GBq6UzW_OkqEWrgwd8Sxn4r10')

            registros = ler_aba_segura(planilha, 'Registro_Diario')
            catalogo = ler_aba_segura(planilha, 'Catalogo_Materiais')
            militares = ler_aba_segura(planilha, 'Militares')
            viaturas_bd = ler_aba_segura(planilha, 'Viaturas')

            # Tenta pegar o número do Chefe de Socorro
            t_socorro = ""
            try:
                config_dados = ler_aba_segura(planilha, 'Configuracoes')
                confs = {str(c.get('cargo')).strip(): str(c.get('telefone_whatsapp')).strip() for c in config_dados if 'cargo' in c}
                t_socorro = confs.get('chefe_socorro', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            except: pass

            lista_contatos = [{'nome': m.get('nome_formatado', ''), 'tel': str(m.get('telefone', '')).replace(' ', '').replace('-', '').replace('(', '').replace(')', '')} for m in militares if m.get('telefone')]
            dict_nomes = {str(m.get('id_material', '')).strip(): str(m.get('nome_material', '')).strip() for m in catalogo}
            
            fuso_br = timezone(timedelta(hours=-3))
            agora = datetime.now(fuso_br)
            hoje_str = agora.strftime('%d/%m/%Y')
            dias = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

            registros_hoje = [r for r in registros if hoje_str in str(r.get('data_hora', ''))]
            ultimos_hoje = {str(r.get('id_material', '')).strip(): r for r in registros_hoje}

            # VERIFICA SE FALTOU CONFERIR ALGUMA VIATURA HOJE
            locais_obrigatorios = [str(v['id_viatura']).strip() for v in viaturas_bd if str(v.get('nome_viatura', '')).strip().lower() != 'almoxarifado' and 'id_viatura' in v]
            vtrs_conferidas = set(str(r.get('id_viatura')).strip() for r in registros_hoje)
            viaturas_pendentes = [loc for loc in locais_obrigatorios if loc not in vtrs_conferidas and loc.replace('ê','e') not in vtrs_conferidas]
            
            aviso_pendencia = f"Você ainda não conferiu estes locais: {', '.join(viaturas_pendentes)}. O seu relatório está incompleto!" if viaturas_pendentes else None

            # AGRUPAR POR CATEGORIA (IGNORAR ONDE ESTÁ A VIATURA)
            agrupamento_cats = {}
            alteracoes = []

            for m_id, r in ultimos_hoje.items():
                if not m_id: continue
                nome_real = dict_nomes.get(m_id, m_id)
                categoria = str(r.get('compartimento_encontrado', 'Sem Categoria')).strip()
                qtd = r.get('qtde_encontrado', 0)
                status = r.get('status_encontrado', '')
                
                if status in ['Operante', 'Movido']:
                    if categoria not in agrupamento_cats: agrupamento_cats[categoria] = []
                    agrupamento_cats[categoria].append(f"{nome_real} - Qtd: {qtd}")
                
                if status != 'Operante': 
                    alteracoes.append(f"[ALTERAÇÃO] *{nome_real}* | Status: {status} | Obs: _{r.get('observacao', '')}_")

            categorias_ordenadas = sorted(agrupamento_cats.keys())

            # CONSTRUIR O TEXTO DO RELATÓRIO
            texto = "*SECRETARIA DE SEGURANÇA PÚBLICA*\n*CORPO DE BOMBEIROS MILITAR DO MARANHÃO*\n*COMANDO OPERACIONAL METROPOLITANO*\n*13º BATALHÃO DE BOMBEIROS MILITAR*\n\n"
            texto += f"*Serviço Operacional do 13° BBM do dia {hoje_str} ({dias[agora.weekday()]})*\n\n"

            if not guarnicao: texto += "GUARNIÇÃO NÃO CADASTRADA\n\n"
            else:
                for militar in guarnicao: texto += f"*{str(militar.get('funcao', '')).upper()}*\n_{militar.get('nome', '')}_\n\n"

            # STATUS DAS VIATURAS
            texto += "*STATUS DAS VIATURAS:*\n"
            if not status_vtrs: texto += "Status não informado na guarnição.\n\n"
            else:
                for vtr in ['ABT_34', 'AR_75']:
                    info = status_vtrs.get(vtr, {})
                    st = info.get('status', 'Operante')
                    obs = info.get('obs', '')
                    texto += f"*{vtr.replace('_', '-')}*: {st}"
                    if obs: texto += f" ({obs})"
                    texto += "\n"
                texto += "\n"

            texto += "*MATERIAIS E EQUIPAMENTOS:*\n\n"
            if categorias_ordenadas:
                for cat in categorias_ordenadas:
                    texto += f"*{cat}*\n"
                    for item in agrupamento_cats[cat]: texto += f"{item}\n"
                    texto += "\n"
            else: texto += "Nenhum material conferido hoje.\n\n"

            texto += "*ALTERAÇÕES GERAIS CADASTRADAS HOJE:*\n"
            if alteracoes: texto += "\n".join(alteracoes)
            else: texto += "Nenhuma alteração registada hoje. [OK]"

            resposta = {
                "sucesso": True, 
                "texto": texto, 
                "t_socorro": t_socorro,
                "contatos": lista_contatos,
                "aviso": aviso_pendencia
            }
        except Exception as e:
            resposta = {"sucesso": False, "mensagem": str(e)}

        self.wfile.write(json.dumps(resposta).encode('utf-8'))
