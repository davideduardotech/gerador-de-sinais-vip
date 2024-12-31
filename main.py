import os, time, random, json, sys
import telebot
import pytz
from datetime import datetime, timedelta
from iqoptionapi.stable_api import IQ_Option
from colorama import Fore, init
import pandas as pd
import numpy as np
import mplfinance as mpl
import secrets
from dotenv import load_dotenv
init(autoreset=True, convert=True)
load_dotenv()

class Horario:
    def __init__(self, timezone="America/Sao_Paulo"):
        self.timezone = pytz.timezone(timezone)

    def now(self):
        return datetime.now(self.timezone)
    def horario_valido(self, horario: str) -> bool:
        """
        Verifica se o horário informado (no formato 'HH:MM') é maior que o horário atual.
        
        Args:
            horario (str): Horário no formato 'HH:MM' (ex.: "14:00").

        Returns:
            bool: True se o horário informado é maior que o horário atual, False caso contrário.
        """
        try:
            # Obter o horário atual no timezone configurado
            agora = datetime.now(self.timezone)
            
            # Combinar a data atual com o horário fornecido
            data_com_horario = datetime.strptime(
                agora.strftime('%Y-%m-%d') + f" {horario}:00", 
                '%Y-%m-%d %H:%M:%S'
            )

            # Ajustar o objeto datetime para o timezone configurado
            data_com_horario = self.timezone.localize(data_com_horario)

            # Verificar se o horário fornecido é maior que o horário atual
            return data_com_horario > agora
        except ValueError:
            return False

    def aguardar_horario(self, horario: str, delay: int = 0):
        """
        Aguarda até que o horário informado (no formato 'HH:MM') seja atingido.
        
        Args:
            horario (str): Horário no formato 'HH:MM' (ex.: "14:00").
        """
        try:
            # Obter a data e horário atual no timezone configurado
            agora = datetime.now(self.timezone)

            # Extrair horas e minutos do horário fornecido
            horas, minutos = map(int, horario.split(':'))

            # Verificar se o horário fornecido pertence ao próximo dia
            data_com_horario = agora.replace(hour=horas, minute=minutos, second=0, microsecond=0)
            if data_com_horario <= agora:
                # Se o horário já passou hoje, ajustar para o dia seguinte
                data_com_horario += timedelta(days=1)

            # Calcular o timestamp do horário da operação e aplicar o delay
            timestemp_da_operacao = int(data_com_horario.timestamp()) - delay

            # Loop para aguardar até o horário ser atingido
            while int(datetime.now(self.timezone).timestamp()) < timestemp_da_operacao:
                time.sleep(1)  # Espera 1 segundo antes de verificar novamente

        except ValueError:
            raise ValueError("Horário inválido. Certifique-se de usar o formato 'HH:MM'.")

    def proximo_horario(self, horario_atual: str) -> str:
        horarios = {
            "00": "01:00", "01": "02:00", "02": "03:00", "03": "04:00",
            "04": "05:00", "05": "06:00", "06": "07:00", "07": "08:00",
            "08": "09:00", "09": "10:00", "10": "11:00", "11": "12:00",
            "12": "13:00", "13": "14:00", "14": "15:00", "15": "16:00",
            "16": "17:00", "17": "18:00", "18": "19:00", "19": "20:00",
            "20": "21:00", "21": "22:00", "22": "23:00", "23": "00:00"
        }
        return horarios[horario_atual.split(":")[0]]

    def timestamp(self, horario: str, deslocamento_minutos: int = 0) -> int:
        """
        Calcula o timestamp baseado no horário fornecido e um deslocamento em minutos.

        Args:
            horario (str): Horário no formato 'HH:MM' (ex.: "14:00").
            deslocamento_minutos (int): Deslocamento em minutos (ex.: 0, +1, +2 para martingale).

        Returns:
            int: Timestamp do horário ajustado.
        """
        # Obter a data atual no timezone configurado
        agora = datetime.now(self.timezone)

        # Combinar a data atual com o horário fornecido
        data_com_horario = datetime.strptime(
            agora.strftime('%Y-%m-%d') + f" {horario}:00", 
            '%Y-%m-%d %H:%M:%S'
        )

        # Ajustar o objeto datetime para o timezone configurado
        data_com_horario = self.timezone.localize(data_com_horario)

        # Adicionar o deslocamento em minutos
        data_com_horario += timedelta(minutes=deslocamento_minutos)

        # Retornar o timestamp
        return int(data_com_horario.timestamp())

class MessageString:
    def __init__(self, botManager):
        self.botManager = botManager

    def header(self):
        return "🚀 | <b>CLUBE DOS INVESTIDORES</b>\n| <i>" + self.botManager.datetime_and_weekday_in_string() + "</i>"

    def send_list_string(self, catalogacao):
        message = f"{self.header()}\n\n"
        message += f"Sinais de <b>{catalogacao['hora_atual']}h</b> a <b>{catalogacao['proxima_hora']}h</b>\n\n"

        for signal in catalogacao["lista"]:
            for ativo in signal:
                for horario in signal[ativo]:
                    if signal[ativo][horario]["dir"].strip() == "PUT":
                        dir = "PUT 🟥"
                    else:
                        dir = "CALL 🟩"
                    sinal = f"{ativo.replace('-op','')} {horario} M1 {dir}\n"
                    message+=sinal
        
        return message

    def active_closed_string(self, operacao):
        return f"{self.header()}\n\n\n| <i>{operacao['ativo'].replace('-op','')} {operacao['horario']} {operacao['timeframe']} {operacao['dir']}</i>\n🔒 ativo {operacao['ativo'].replace('-op','')} fechado no momento"
    def time_has_expired_string(self, operacao):
        return f"{self.header()}\n\n\n| <i>{operacao['ativo'].replace('-op','')} {operacao['horario']} {operacao['timeframe']} {operacao['dir']}</i>\n⏰ horário da operação <i>{operacao['horario']}</i> expirou"
    def awaiting_operation_string(self, operacao):
        return f"{self.header()}\n\n| <b>Aguardando Operação</b>\n{operacao['ativo'].replace('-op','')} {operacao['horario']} {operacao['timeframe']} {'CALL 🟩' if operacao['dir'].strip() == 'CALL' else 'PUT 🟥'}"
    def operacao_realizada_string(self, operacao):
        return f"{self.header()}\n\n⏰ Operação Realizada no ativo {operacao['ativo'].replace('-op','')}, aguardando resultado..."
    def resultado_da_operacao_string(self, operacao, resultado, aguardando_martingale=0):
        mensagem = f'{self.header()}\n\n\n| {operacao["ativo"].replace("-op","")} {operacao["horario"]} {operacao["timeframe"]} {operacao["dir"]}\n{resultado}'
        

        if aguardando_martingale == 1 or aguardando_martingale == 2:  # Para 'Nenhum Martingale' ou '1° Martingale'
            mensagem += f"\n\n\n🔄 Operação Realizada({aguardando_martingale}° Martingale) no ativo {operacao['ativo'].replace('-op','')}, aguardando resultado..."
        

        return mensagem
    def resultado_e_placar_da_lista_string(self, catalogacao):
        message = f"{self.header()}\n\n"
        message += f"Sinais de <b>{catalogacao['hora_atual']}h</b> a <b>{catalogacao['proxima_hora']}h</b>\n\n"
        wins = 0
        losses = 0
        for signal in catalogacao["lista"]:
            for ativo in signal:
                for horario in signal[ativo]:
                    direcao = signal[ativo][horario]["dir"].strip()
                    resultado_string = '▫️'
                    if "resultado" in signal[ativo][horario]:
                        resultado = signal[ativo][horario]["resultado"]
                        if resultado["status"] == "win":
                            wins += 1
                            resultado_string = f"✅(g{resultado['martingale']})" if resultado['martingale'] > 0 else "✅"
                        elif resultado["status"] == "loss":
                            losses += 1
                            resultado_string = f"❌" if resultado['martingale'] > 0 else "❌"
                        else:
                            resultado_string = f"▫️"
                        

                    sinal = f"{ativo.replace('-op','')} {horario} M1 {direcao} {resultado_string}\n"
                    message+=sinal
        
        message+=f'\nPlacar: {wins}x{losses}'
        return message



class Catalogador:
    def __init__(self, botManager):
        self.botManager = botManager

    def excluir_imagem(self,nome_imagem, diretorio='temporary images'):
        """Exclui a imagem do diretório especificado."""
        caminho_imagem = os.path.join(diretorio, nome_imagem)
        
        # Verifica se o arquivo existe antes de tentar excluir
        if os.path.isfile(caminho_imagem):
            try:
                os.remove(caminho_imagem)
                self.botManager.logging(f"{Fore.GREEN}[TEMPORARY IMAGES]{Fore.RESET}", f"imagem {nome_imagem} excluída")
            except Exception as e:
                self.botManager.logging(f"{Fore.RED}[TEMPORARY IMAGES]{Fore.RESET}", f"erro ao excluir a imagem {nome_imagem}. Erro: {e}")
        else:
            self.botManager.logging(f"{Fore.RED}[TEMPORARY IMAGES]{Fore.RESET}", f"imagem {nome_imagem} não encontrada no diretório {diretorio}.")
            
            
    
    def gerar_imagem(self,velas, titulo, subtitulo):
        titulo = titulo.replace('-op','')
        """for vela in velas:
            print(datetime.fromtimestamp(vela['from']).strftime(
                '%d/%m/%Y %H:%M:%S'), 'max: {}'.format(vela['max']), 'min: {}'.format(vela['min']))"""

        data = {'open': [],
                'close': [],
                'high': [],
                'low': [],
                'volume': []}
        data_range = []

        for vela in velas:
            data['open'].append(vela['open'])
            data['close'].append(vela['close'])
            data['high'].append(vela['max'])
            data['low'].append(vela['min'])
            data['volume'].append(vela['volume'])
            data_range.append(datetime.fromtimestamp(
                vela['from']).strftime('%d/%m/%Y %H:%M:%S'))

        # create DataFrame
        prices = pd.DataFrame(data,
                            index=data_range)

        """"""
        # display DataFrame
        prices.index = pd.DatetimeIndex(prices.index)

        # $ Markup
        signal = [np.nan for i in range(len(velas)-1)]
        signal.append(velas[-1]['min']-0.00008 if velas[-1]['open'] < velas[-1]['close'] else velas[-1]
                    ['max']+0.00008 if velas[-1]['open'] > velas[-1]['close'] else velas[-1]['max']+0.00008)
        apd = mpl.make_addplot(signal, type='scatter', markersize=100, marker='^' if velas[-1]['open'] < velas[-1]['close'] else 'v' if velas[-1]['open'] > velas[-1]
                            ['close'] else '.', color='#19b76f' if velas[-1]['open'] < velas[-1]['close'] else '#fd4446' if velas[-1]['open'] > velas[-1]['close'] else 'gray')

        # $ create fig
        fig, axlist = mpl.plot(
            prices,
            type="candle",
            title=titulo,
            ylabel='',
            ylabel_lower='',
            volume=True,
            style="yahoo",
            returnfig=True,
            datetime_format='%H:%M:%S',
            addplot=apd
        )

        # add a new suptitle
        fig.suptitle(titulo, y=1.05, fontsize=20, fontfamily='Arial', x=0.59)

        # add a title the the correct axes
        # print('\n\nSUBTITULO[Candlestick]:',subtitulo,'\n\n')
        axlist[0].set_title(subtitulo, fontsize=15,
                            fontfamily='Arial', loc='center')

        # annoted

        # save the figure
        nome_da_imagem = 'image-'+secrets.token_hex(25)
        while True:
            if os.path.isfile('temporary images/{}.png'.format(nome_da_imagem)):
                nome_da_imagem = 'image-'+secrets.token_hex(25)
            else:
                break

        fig.savefig(
            'temporary images/{}.png'.format(nome_da_imagem), bbox_inches='tight')
        return nome_da_imagem+'.png'


    def gerar_configuracao_aleatoria(self,configuracoes, timeframe=None):
        """Define configurações automáticas para catalogação"""
        configuracoes.update({
            "tipo de catalogação": "agressivo",
            "timeframe": timeframe or random.choice(['1 minuto', '5 minutos', '15 minutos']),
            "periodo de catalogação em dias": random.choice(['5 dias', '6 dias', '7 dias', '8 dias', '9 dias', '10 dias']),
            "martingale": "1 martingale",
            "porcentagem de assertividade(nenhum martingale)": random.choice(['78%', '80%']),
            "porcentagem de assertividade(1 martingale)": random.choice(['60%', '70%']),
            "porcentagem de assertividade(2 martingale)": random.choice(['60%', '70%']),  # Evita repetição manual
            "quantidade de operações que a Machine Learning ira filtrar": 20
        })

        return configuracoes
    
    def cataloga(self,par, dias, timeframe):
        data = []
        datas_testadas = []
        time_ = time.time()
        start_timer = time.time() #$ Contagem de Tempo | Inicio
        sair = False
        while sair == False:
            try:
                velas = self.botManager.api_iqoption.get_candles(par, (timeframe * 60), 1000, time_)
            except Exception as erro:
                self.botManager.logging(f"{Fore.RED}[CATALOGAÇÃO]{Fore.RESET}", f"ocorreu um erro ao tentar buscar candles na IQOption com get_candles(): {erro}")
                raise Exception()
            velas.reverse()
            
            for x in velas:
                if datetime.fromtimestamp(x['from']).strftime('%Y-%m-%d') not in datas_testadas:
                    datas_testadas.append(datetime.fromtimestamp(
                        x['from']).strftime('%Y-%m-%d'))

                if len(datas_testadas) <= dias:
                    x.update({'cor': 'verde' if x['open'] < x['close']
                            else 'vermelha' if x['open'] > x['close'] else 'doji'})
                    data.append(x)
                else:
                    sair = True
                    break
            
            


            time_ = int(velas[-1]['from'] - 1)

        analise = {}
        for velas in data:
            horario = datetime.fromtimestamp(velas['from']).strftime('%H:%M')
            if horario not in analise:
                analise.update(
                    {horario: {'verde': 0, 'vermelha': 0, 'doji': 0, '%': 0, 'dir': ''}})
            analise[horario][velas['cor']] += 1

            try:
                analise[horario]['%'] = round(100 * (analise[horario]['verde'] / (
                    analise[horario]['verde'] + analise[horario]['vermelha'] + analise[horario]['doji'])))
            except:
                pass

        for horario in analise:
            if analise[horario]['%'] > 50:
                analise[horario]['dir'] = 'CALL'
            if analise[horario]['%'] < 50:
                analise[horario]['%'], analise[horario]['dir'] = 100 - \
                    analise[horario]['%'], 'PUT '
                    
                    
        end_timer = time.time() #$ Contagem de Tempo | Final
        
        """
        CODDING: Log
        """
        self.botManager.logging(f"{Fore.GREEN}[CATALOGAÇÃO]{Fore.RESET}", f"ativo catalogado: {par} | {dias} dias{Fore.LIGHTBLACK_EX}(demorou {abs(end_timer-start_timer)} segundos){Fore.RESET}")
        return analise

    def organizar_catalogacao_por_horario(self,catalogacao):
        """
        Organiza os dados de catalogação por horários específicos, agrupando-os de acordo com a hora base 
        (por exemplo, '23:45' será agrupado em '23:00') e garantindo que os dados de cada ativo sejam 
        agrupados corretamente dentro dessas faixas de horário.

        Exemplo de entrada:
        catalogacao = {
            "EURUSD": {
                "05:00": {'verde': 6, 'vermelha': 0, 'doji': 0, '%': 100, 'dir': 'CALL'},
                "06:00": {'verde': 3, 'vermelha': 2, 'doji': 0, '%': 60, 'dir': 'CALL'},
                ...
            },
            "GBPUSD": {
                "05:00": {'verde': 5, 'vermelha': 1, 'doji': 0, '%': 83, 'dir': 'CALL'},
                "06:00": {'verde': 4, 'vermelha': 2, 'doji': 0, '%': 67, 'dir': 'CALL'},
                ...
            }
        }
        
        Exemplo de saída (dados organizados por hora base):
        {
            "05:00": {
                "EURUSD": {
                    "05:00": {'verde': 6, 'vermelha': 0, 'doji': 0, '%': 100, 'dir': 'CALL'}
                },
                "GBPUSD": {
                    "05:00": {'verde': 5, 'vermelha': 1, 'doji': 0, '%': 83, 'dir': 'CALL'}
                }
            },
            "06:00": {
                "EURUSD": {
                    "06:00": {'verde': 3, 'vermelha': 2, 'doji': 0, '%': 60, 'dir': 'CALL'}
                },
                "GBPUSD": {
                    "06:00": {'verde': 4, 'vermelha': 2, 'doji': 0, '%': 67, 'dir': 'CALL'}
                }
            },
            ...
        }

        Como funciona:
        1. O código gera uma lista de períodos de hora (de "00:00" a "23:00").
        2. Em seguida, cria um dicionário (`horarios_organizados`) onde cada chave corresponde a um período 
        de hora (exemplo: "00:00", "01:00", ..., "23:00").
        3. Para cada par de ativo na `catalogacao`, percorre os horários e coloca os dados de cada horário 
        dentro do intervalo de hora base correspondente. Ou seja, qualquer horário do tipo 'HH:MM' será 
        agrupado com a hora base 'HH:00', sendo assim, '23:45' será agrupado em '23:00'.
        4. O dicionário final (`horarios_organizados`) contém os ativos agrupados dentro de cada hora base 
        com os dados correspondentes de cada intervalo de tempo.

        Parâmetros:
        - catalogacao (dict): Dicionário com dados de ativos, onde as chaves são os pares de moedas/ativos 
        (ex: "EURUSD") e os valores são dicionários de horários com informações sobre cada intervalo de tempo.

        Retorno:
        - dict: Um dicionário com os dados reorganizados por períodos de hora base. Cada chave é uma hora base 
        ("00:00", "01:00", etc.), e o valor é outro dicionário contendo os pares de ativos e seus dados 
        correspondentes para aquele período de hora.

        Exemplo:
        Entrada:
        {
            "EURUSD": {
                "05:00": {'verde': 6, 'vermelha': 0, 'doji': 0, '%': 100, 'dir': 'CALL'},
                "06:00": {'verde': 3, 'vermelha': 2, 'doji': 0, '%': 60, 'dir': 'CALL'}
            }
        }

        Saída:
        {
            "05:00": {
                "EURUSD": {
                    "05:00": {'verde': 6, 'vermelha': 0, 'doji': 0, '%': 100, 'dir': 'CALL'}
                }
            },
            "06:00": {
                "EURUSD": {
                    "06:00": {'verde': 3, 'vermelha': 2, 'doji': 0, '%': 60, 'dir': 'CALL'}
                }
            }
        }
        """
        # Lista de períodos de hora
        periodos_horas = [f"{h:02}:00" for h in range(24)]
        
        # Dicionário organizado por horários
        horarios_organizados = {periodo: {} for periodo in periodos_horas}

        # Percorrer os ativos e horários na catalogação
        for par, horarios in catalogacao.items():
            for horario, dados in horarios.items():
                # Identificar a hora base do horário (e.g., '23:45' -> '23:00')
                hora_base = f"{horario[:2]}:00"
                
                # Verificar se a hora base está dentro dos períodos de horas definidos
                if hora_base in periodos_horas:
                    # Adicionar o ativo e horário na estrutura organizada
                    if par not in horarios_organizados[hora_base]:
                        horarios_organizados[hora_base][par] = {}
                    
                    horarios_organizados[hora_base][par][horario] = dados
        
        return horarios_organizados
        
    def catalogar_operacoes(self,configuracoes):
        ativos = self.botManager.api_iqoption.get_all_open_time()
        start_time_all = time.time()
        self.botManager.logging(f"{Fore.GREEN}[CATALOGAÇÃO]{Fore.RESET}", "catalogação iniciada pra filtrar novas operações...")
        
        catalogacao = {}
        for par in ativos['digital']:
            if ativos['digital'][par]['open'] == True:
                timer = int(time.time())
                
                try:
                    catalogacao.update({par: self.cataloga(par, int(configuracoes['periodo de catalogação em dias'].split(' ')[0]), int(configuracoes['timeframe'].split(' ')[0]))})
                except Exception as error:
                    #print(f"@Catalogador | @Function catalogar_operacoes_rapidas(try/catch) | ocorreu um erro ao tentar usar catalogacao.update({...}) | @Error {error}")
                    continue
                    #raise Exception(f"@Catalogador | @Function catalogar_operacoes_rapidas(try/catch) | ocorreu um erro ao tentar usar catalogacao.update({...}) | @Error {error}")

                # print('Depois da catalogação Finalizada do ativo {}'.format(par))

                for par in catalogacao:
                    for horario in sorted(catalogacao[par]): # horario -> %H:%M -> 21:00
                        if configuracoes['martingale'].strip() != '':
                            # print(horario)
                            mg_time = horario
                            soma = {'verde': catalogacao[par][horario]['verde'], 'vermelha': catalogacao[par]
                                    [horario]['vermelha'], 'doji': catalogacao[par][horario]['doji']}

                            for i in range(int(configuracoes['martingale'].split(' ')[0])):

                                catalogacao[par][horario].update({'mg'+str(i+1): {'verde': 0, 'vermelha': 0, 'doji': 0, '%': 0}})

                                # calcular horario do martingale, exemplo: '21:00'(mg0) --> '21:01'(mg1) --> '21:02'(mg2)
                                mg_time = (datetime.strptime(f"{datetime.now():%Y-%m-%d} {mg_time}", '%Y-%m-%d %H:%M') + timedelta(minutes=int(configuracoes['timeframe'].split()[0]))).strftime('%H:%M')

                                
                                if mg_time in catalogacao[par]:
                                    catalogacao[par][horario]['mg'+str(i+1)]['verde'] += catalogacao[par][mg_time]['verde'] + soma['verde']
                                    catalogacao[par][horario]['mg'+str(i+1)]['vermelha'] += catalogacao[par][mg_time]['vermelha'] + soma['vermelha']
                                    catalogacao[par][horario]['mg'+str(i+1)]['doji'] += catalogacao[par][mg_time]['doji'] + soma['doji']

                                    catalogacao[par][horario]['mg'+str(i+1)]['%'] = round(100 * (catalogacao[par][horario]['mg'+str(i+1)]['verde' if catalogacao[par][horario]['dir'] == 'CALL' else 'vermelha'] / (
                                        catalogacao[par][horario]['mg'+str(i+1)]['verde'] + catalogacao[par][horario]['mg'+str(i+1)]['vermelha'] + catalogacao[par][horario]['mg'+str(i+1)]['doji'])))

                                    soma['verde'] += catalogacao[par][mg_time]['verde']
                                    soma['vermelha'] += catalogacao[par][mg_time]['vermelha']
                                    soma['doji'] += catalogacao[par][mg_time]['doji']
                                else:
                                    catalogacao[par][horario]['mg' +
                                                                str(i+1)]['%'] = 'N/A'

        end_time_all = time.time()
        logging(f"{Fore.GREEN}[CATALOGAÇÃO]{Fore.RESET}", f"catalogação finalizada em todos ativos{Fore.LIGHTBLACK_EX}(demorou {abs(end_time_all-start_time_all)} segundos){Fore.RESET}")
        
        catalogacao_organizada = self.organizar_catalogacao_por_horario(catalogacao)
        return catalogacao_organizada
    
    def filtrar_lista_de_operacoes_por_horario(self,catalogacao_organizada, configuracoes):
        """
        Filtra as operações de acordo com o horário atual e período de uma hora.

        Args:
            catalogacao_organizada (dict): Dicionário de catalogação organizado por horários.
            configuracoes (dict): Configurações para o filtro, incluindo parâmetros de martingale e assertividade.

        Returns:
            list: Lista de operações filtradas no formato [{ativo: {horario: dados}}].
        """
        # Obter o horário atual
        agora = datetime.now()
        hora_atual = agora.strftime("%H:00")
        minuto_atual = agora.minute

        """# Verificar se o minuto é maior ou igual a 50
        if minuto_atual >= 50:
            print(f"Horário atual é {agora.strftime('%H:%M')}. Aguarde o próximo ciclo horário.")
            return []"""

        # Determinar o período de hora (exemplo: 14:00 - 15:00)
        proxima_hora = (agora + timedelta(hours=1)).strftime("%H:00")

        # Obter os dados do catálogo para o período atual
        catalogo_horario_atual = catalogacao_organizada.get(hora_atual, {})

        lista_operacoes = []

        for ativo, sinais in catalogo_horario_atual.items():
            for horario, dados in sinais.items():
                # Filtrar apenas os sinais após o horário atual
                hora_sinal = datetime.strptime(f"{datetime.now().strftime('%d/%m/%Y')} {horario}", "%d/%m/%Y %H:%M")
                if hora_sinal.timestamp() >= agora.timestamp():
                    
                    # Verificar assertividade com base nas configurações
                    if configuracoes["martingale"] == "":
                        if dados['%'] >= int(configuracoes['porcentagem de assertividade(nenhum martingale)'].replace('%', '')):
                            lista_operacoes.append({ativo: {horario: dados}})
                    elif configuracoes["martingale"] == "1 martingale":
                        if dados['%'] >= int(configuracoes['porcentagem de assertividade(nenhum martingale)'].replace('%', '')) and \
                        dados['mg1']['%'] >= int(configuracoes['porcentagem de assertividade(1 martingale)'].replace('%', '')):
                            lista_operacoes.append({ativo: {horario: dados}})
                    elif configuracoes["martingale"] == "2 martingale":
                        if dados['%'] >= int(configuracoes['porcentagem de assertividade(nenhum martingale)'].replace('%', '')) and \
                        dados['mg1']['%'] >= int(configuracoes['porcentagem de assertividade(1 martingale)'].replace('%', '')) and \
                        dados['mg2']['%'] >= int(configuracoes['porcentagem de assertividade(2 martingale)'].replace('%', '')):
                            lista_operacoes.append({ativo: {horario: dados}})

        self.botManager.logging(f"{Fore.GREEN}[CATALOGAÇÂO]{Fore.RESET}", f"Operações filtradas entre {hora_atual} e {proxima_hora}: {len(lista_operacoes)} encontradas.")
        return {"hora_atual": hora_atual, "proxima_hora": proxima_hora ,"lista":lista_operacoes}
    
    def ordenar_lista(self,lista, timeframe=1):
        """
        Ordena e filtra operações para garantir que haja um intervalo mínimo entre elas.
        
        Args:
            lista (list): Lista de operações no formato [{'ativo': {'horario': dados}}, ...].
            timeframe (int): Timeframe em minutos. O intervalo mínimo entre operações será timeframe * 60 segundos.
        
        Returns:
            list: Lista filtrada e ordenada de operações.
        """
        # Converter o timeframe para o intervalo mínimo em minutos
        intervalo_minimo = ((timeframe*4) * 60)
        
        # Criar uma lista de operações com horários convertidos para datetime
        operacoes_formatadas = []
        for operacao in lista:
            for ativo, dados in operacao.items():
                for horario, detalhes in dados.items():
                    # Converter o horário em datetime para facilitar a comparação
                    horario_completo = datetime.strptime(f"{datetime.now().strftime('%d/%m/%Y')} {horario}", "%d/%m/%Y %H:%M")
                    operacoes_formatadas.append({'ativo': ativo, 'horario': horario_completo, 'dados': detalhes})
        
        # Ordenar as operações pelo horário
        operacoes_formatadas.sort(key=lambda x: x['horario'])
        
        # Filtrar operações para garantir o intervalo mínimo
        lista_filtrada = []
        ultimo_horario = None
        
        for operacao in operacoes_formatadas:
            if ultimo_horario is None or (operacao['horario'] - ultimo_horario).total_seconds() >= intervalo_minimo:
                lista_filtrada.append(operacao)
                ultimo_horario = operacao['horario']
        
        # Converter de volta para o formato original
        lista_resultado = []
        for operacao in lista_filtrada:
            lista_resultado.append({
                operacao['ativo']: {
                    operacao['horario'].strftime('%H:%M'): operacao['dados']
                }
            })
        
        return lista_resultado

    def gerar_lista(self):
        configuracoes = self.gerar_configuracao_aleatoria({})
        catalogacao = self.catalogar_operacoes(configuracoes)
        lista_dicionario = self.filtrar_lista_de_operacoes_por_horario(catalogacao, configuracoes) 
        lista = self.ordenar_lista(lista_dicionario["lista"]) 
        return {"hora_atual": lista_dicionario["hora_atual"], "proxima_hora": lista_dicionario["proxima_hora"] ,"lista": lista}


    def checar_ativo_aberto_na_iqoption(self, ativo):
        try:
            ativos = self.botManager.api_iqoption.get_all_open_time()
            if ativos['digital'][ativo]['open']:
                return True
            else:
                return False
        except:
            return False

    def sendPhoto(self, nome_da_imagem, operacao, resultado, aguardando_martingale=0):
        self.botManager.api_telegram.send_photo(
            chat_id=self.botManager.id_grupo_telegram, 
            photo=open(f'temporary images/{nome_da_imagem}', 'rb'), 
            caption=self.botManager.messageString.resultado_da_operacao_string(operacao=operacao,resultado=resultado, aguardando_martingale=aguardando_martingale)
        )
    def sendStick(self, resultado_atual, tipo):
        if tipo == "win":
            if resultado_atual == 'Nenhum Martingale':
                sticker_path = 'sticks/win-sem-gale.webp'
            else:  # Para '1° Martingale' ou '2° Martingale'
                sticker_path = 'sticks/win-no-gale.webp'
            self.botManager.api_telegram.send_sticker(chat_id=self.botManager.id_grupo_telegram, sticker=open(sticker_path, 'rb'))
        
        if tipo == "loss":
            sticker_path = 'sticks/loss.webp'
            self.botManager.api_telegram.send_sticker(chat_id=self.botManager.id_grupo_telegram, sticker=open(sticker_path, 'rb'))

        if tipo == "doji":
            sticker_path = 'sticks/doji.webp'
            self.botManager.api_telegram.send_sticker(chat_id=self.botManager.id_grupo_telegram, sticker=open(sticker_path, 'rb'))                           

    def acompanhar_operacoes(self, lista, timeframe=1):
        for signal in lista:
            for ativo in signal:
                for horario in signal[ativo]:
                    ativo_operacao = ativo
                    horario_operacao = horario
                    direcao_operacao = signal[ativo][horario]["dir"].strip()
                    timeframe_operacao = timeframe
                    operacao = {"ativo":ativo_operacao, "horario":horario_operacao, "timeframe":f"M{timeframe_operacao}", "dir":direcao_operacao}

                    if self.botManager.horario.horario_valido(horario):
                        if self.checar_ativo_aberto_na_iqoption(ativo):
                            # aguardando operação
                            self.botManager.api_telegram.send_message(self.botManager.id_grupo_telegram, self.botManager.messageString.awaiting_operation_string(operacao))
                            
                            # aguardar horario da operação
                            self.botManager.horario.aguardar_horario(horario_operacao)

                            # operação realizada 
                            self.botManager.api_telegram.send_message(self.botManager.id_grupo_telegram, self.botManager.messageString.operacao_realizada_string(operacao))

                            resultados = ['Nenhum Martingale', '1° Martingale', '2° Martingale']
                            for i, resultado_atual in enumerate(resultados):
                                # Espera o tempo apropriado
                                time.sleep(timeframe_operacao * 60)
                                

                                timestamp_operacao = self.botManager.horario.timestamp(horario_operacao, deslocamento_minutos=timeframe_operacao * i)

                                vela = self.botManager.api_iqoption.get_candles(ativo_operacao, timeframe_operacao * 60, 1, timestamp_operacao)[0]
                                cor = 'vermelha' if vela['open'] > vela['close'] else 'verde' if vela['open'] < vela['close'] else 'doji'
                                velas = self.botManager.api_iqoption.get_candles(ativo_operacao, timeframe_operacao*60, 15, timestamp_operacao)

                                if cor != 'doji':
                                   
                                    if (cor == 'vermelha' and direcao_operacao == 'PUT') or (cor == 'verde' and direcao_operacao == 'CALL'):
                                        resultado = 'win'
                                    elif (cor == 'vermelha' and direcao_operacao == 'CALL') or (cor == 'verde' and direcao_operacao == 'PUT'):
                                        resultado = 'loss'
                                    else:
                                        resultado = ''

                                    if resultado == 'win':
                                        
                                        # 1. gerar imagem
                                        nome_da_imagem = self.gerar_imagem(velas=velas, titulo=ativo_operacao, subtitulo=f'Win +R$({resultado_atual})')
                                        
                                        # 2. enviando imagem com mensagem de win(+R$)
                                        self.sendPhoto(nome_da_imagem, operacao, f'<b>Win +R$({resultado_atual})</b>')
                                        
                                        # 3. enviar stick de "win"
                                        self.sendStick(resultado_atual, 'win')

                                        # 3. excluir Imagem
                                        self.excluir_imagem(nome_da_imagem)

                                        # 4. adicionar win na lista pra mostrar resultado depois
                                        signal[ativo_operacao][horario_operacao]["resultado"] = {"status":"win", "message":f"<b>Win +R$({resultado_atual})</b>", "martingale":i}
                                        
                                        break  # Parar o loop se o resultado for 'win'

                                    elif resultado == 'loss':
                                        # 1. gerar imagem
                                        nome_da_imagem = self.gerar_imagem(velas=velas, titulo=ativo_operacao, subtitulo=f'Loss -R$({resultado_atual})')
                                        
                                        
                                        # 2. enviar mensagem de loss(-R$) com a imagem gerada
                                        self.sendPhoto(nome_da_imagem, operacao, f'<b>Loss -R$({resultado_atual})</b>', aguardando_martingale=i+1)
                                                                                
                                        # 3. excluir imagem
                                        self.excluir_imagem(nome_da_imagem)

                                        # 4. enviar stick
                                        if resultado_atual == "2° Martingale":
                                            self.sendStick(resultado_atual, 'loss')
                                            
                                            # 4. adicionar loss na lista pra mostrar resultado depois
                                            signal[ativo_operacao][horario_operacao]["resultado"] = {"status":"loss", "message":f"<b>Loss -R$({resultado_atual})</b>", "martingale":i}
                                        

                                            
                                        
                                        

                                else:  # Se for um DOJI
                                    if resultado_atual == '2° Martingale':
                                        # 1. gerar imagem
                                        nome_da_imagem = self.gerar_imagem(velas=velas, titulo=ativo_operacao, subtitulo=f'DOJI detectado ({resultado_atual})')

                                        # 2. enviar imagem com a mensage 
                                        self.sendPhoto(nome_da_imagem, operacao, f'🔍 DOJI detectado no ativo <i>{ativo_operacao}</i>') 
                                        
                                        # 3. enviar stick
                                        self.sendStick(resultado_atual, 'doji')

                                        # 4. excluir imagem
                                        self.excluir_imagem(nome_da_imagem)

                                        
                                        # 4. adicionar resultado na lista pra mostrar resultado depois
                                        signal[ativo_operacao][horario_operacao]["resultado"] = {"status":"doji", "message":f"<b>DOJI detectado({resultado_atual})</b>", "martingale":i}
                                        
                                        
                                        time.sleep(10)

                                        break  # Finalizar porque atingiu o limite de martingale
                                    else:
                                        # 1. gerar imagem
                                        nome_da_imagem = self.gerar_imagem(velas=velas, titulo=ativo_operacao, subtitulo=f'DOJI detectado ({resultado_atual})')

                                        # 2. enviar imagem 
                                        self.sendPhoto(nome_da_imagem, operacao, f'🔍 DOJI detectado no ativo <i>{ativo_operacao}</i>', aguardando_martingale=i+1)
                                        
                                        # 3. enviar stick
                                        self.sendStick(resultado_atual, 'doji')

                                        # 4. excluir imagem
                                        self.excluir_imagem(nome_da_imagem)
                                        
                                        time.sleep(10)
                                        continue  # Continuar para o próximo gale
                                

                        else:
                            # ativo fechado
                            self.botManager.api_telegram.send_message(self.botManager.id_grupo_telegram, self.botManager.messageString.active_closed_string(operacao))
                        
                    else:
                        # horario da operacao expirado
                        self.botManager.api_telegram.send_message(self.botManager.id_grupo_telegram, self.botManager.messageString.time_has_expired_string(operacao))

        return lista

class BotManager:
    def __init__(self):
        self.email_iqoption = os.getenv("EMAIL_IQOPTION")
        self.senha_iqoption = os.getenv("SENHA_IQOPTION")
        self.token_telegram_bot = os.getenv("TOKEN_TELEGRAM_BOT")
        self.id_grupo_telegram = os.getenv("ID_GRUPO_TELEGRAM")

        self.api_telegram = telebot.TeleBot(self.token_telegram_bot, parse_mode='HTML')
        self.api_iqoption = None

        self.messageString = MessageString(self)

        self.horario = Horario()

        self.catalogador = Catalogador(self)
        
    
    def datetime_and_weekday_in_string(self): 
        days = ['Segunda-Feira','Terça-feira','Quarta-feira','Quinta-feira','Sexta-feira','Sábado','Domingo']
        return '{}, {}'.format(datetime.fromtimestamp(datetime.utcnow().timestamp() - 10800).strftime('%d/%m/%Y %H:%M:%S'),days[datetime.fromtimestamp(datetime.utcnow().timestamp() - 10800).weekday()] )

    def logging(self, info, message):
        print(f"{Fore.LIGHTBLACK_EX}[LOG]{Fore.RESET}{info} {Fore.LIGHTBLACK_EX}{self.datetime_and_weekday_in_string()}{Fore.RESET} {message}")

    def conectar_iqoption(self):
        while True:
            try:
                self.api_iqoption = IQ_Option(self.email_iqoption, self.senha_iqoption)
                self.api_iqoption.connect()
                if self.api_iqoption.check_connect():
                    saldo = self.api_iqoption.get_balance()
                    self.logging(f"{Fore.GREEN}[IQ OPTION]{Fore.RESET}", f"conectada, banca atual R${saldo} (Conta de Treinamento)")
                    return self.api_iqoption
                else:
                    self.logging(f"{Fore.RED}[IQ OPTION]{Fore.RESET}", "Erro ao conectar na IQ Option. Tentando novamente...")
            except Exception as erro:
                self.logging(f"{Fore.RED}[IQ OPTION]{Fore.RESET}", f"Erro ao conectar na IQ Option: {erro}")
                time.sleep(2)
    
    

    def start(self):
        while True:
            try:
                # 1. gerar lista
                catalogacao = self.catalogador.gerar_lista()
                
                if len(catalogacao["lista"]) < 3:
                    minutos = int(self.horario.now().strftime('%M'))
                    if minutos >= 50:
                        horario_atual = self.horario.now().strftime('%H:%M')
                        proximo_horario = self.horario.proximo_horario(horario_atual)
                        self.logging(f"{Fore.GREEN}[BOTMANAGER]{Fore.RESET}",f"poucas operacoes encontradas no horario atual {Fore.LIGHTBLACK_EX}{self.horario.now().strftime('%d/%m/%Y %H:%M:%S')}{Fore.RESET} aguardando o proximo horario {Fore.LIGHTBLACK_EX}{proximo_horario}{Fore.RESET} para tentar novamente")
                        self.horario.aguardar_horario(proximo_horario) # Aguarda até a próxima hora

                    continue
                
                # 2. enviar lista no telegram
                self.api_telegram.send_message(self.id_grupo_telegram, self.messageString.send_list_string(catalogacao))

                # 3. acompanhar resultado da lista
                lista = self.catalogador.acompanhar_operacoes(catalogacao["lista"])

                # 4. enviar resultado da lista
                catalogacao["lista"] = lista
                self.api_telegram.send_message(self.id_grupo_telegram, self.messageString.resultado_e_placar_da_lista_string(catalogacao))
                
                # 5. aguardar proxima hora, caso necessário
                if self.horario.horario_valido(catalogacao["proxima_hora"]):
                    self.logging(f"{Fore.GREEN}[BOTMANAGER]{Fore.RESET}",f"{len(catalogacao['lista'])} operações finalizadas, aguardando horario {Fore.LIGHTBLACK_EX}{catalogacao['proxima_hora']}{Fore.RESET} para catalogar mais operações")
                    self.horario.aguardar_horario(catalogacao["proxima_hora"])
                else:
                    self.logging(f"{Fore.GREEN}[BOTMANAGER]{Fore.RESET}",f"{len(catalogacao['lista'])} operações finalizadas, catalogando novas operações")
                    

                
            except Exception as error:
                self.logging(f"{Fore.RED}[BOTMANAGER]{Fore.RESET}", f"Erro na função BotManager.start(): {error}")
                

    def iniciar(self):
        """Inicializa o bot."""
        print("| Detalhes")
        print("Desenvolvedor: David Eduardo (https://github.com/davideduardotech)")
      
        
        self.conectar_iqoption()    
        self.start()


if __name__ == "__main__":
    bot_manager = BotManager()
    bot_manager.iniciar()



