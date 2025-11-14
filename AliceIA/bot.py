# bot.py - ALICE IA: RÁPIDA, COM MEMÓRIA, EMOJIS REAIS E COMANDOS
import discord
import ollama
import os
import json
import random
import atexit
import requests
from bs4 import BeautifulSoup
import re

# === TOKEN DIRETO (NUNCA COMPARTILHE!) ===
TOKEN = 'Seu token ficaria aqui'  # ← COLE SEU TOKEN REGENERADO!

if TOKEN == 'SEU_NOVO_TOKEN_AQUI' or not TOKEN:
    print("ERRO: COLOQUE SEU TOKEN NO CÓDIGO!")
    exit()

# === CAMINHO DOS ARQUIVOS ===
caminho_pasta = os.path.dirname(__file__)
caminho_json = os.path.join(caminho_pasta, 'personalidade.json')
caminho_historico = os.path.join(caminho_pasta, 'historico.json')

# === CARREGA PERSONALIDADE ===
try:
    with open(caminho_json, 'r', encoding='utf-8') as f:
        personalidade = json.load(f)
    print(f"Personalidade carregada: {personalidade['nome']}")
    print(f"DEBUG: Chaves disponíveis no estilo_escrita: {list(personalidade['estilo_escrita'].keys())}")
except Exception as e:
    print(f"ERRO: personalidade.json não encontrado! → {e}")
    exit()

# === CARREGA HISTÓRICO ===
historico = {}
try:
    with open(caminho_historico, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print(f"DEBUG: Data carregada do JSON: {data}")  # DEBUG
        # Converte todas as chaves para string
        historico = {str(k): v for k, v in data.items()}
    print(f"DEBUG: Histórico após conversão: {historico}")  # DEBUG
    print(f"Histórico carregado: {len(historico)} usuários")

    # DEBUG: Mostra quantas mensagens por usuário
    for user_id, msgs in historico.items():
        print(f"DEBUG: User {user_id}: {len(msgs)} mensagens")

except FileNotFoundError:
    print("historico.json não encontrado. Criando novo.")
    historico = {}
except json.JSONDecodeError as e:
    print(f"ERRO JSON: Arquivo corrompido - {e}")
    historico = {}
except Exception as e:
    print(f"Erro ao carregar histórico: {e}")
    historico = {}

# === CONFIGURAÇÕES ===
MODEL = 'phi3:mini'
PALAVRAS_BUSCA = ['o que é', 'quem é', 'quando foi', 'onde fica', 'atual', 'notícia', 'pesquisa']

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === CACHE DE RESPOSTAS RÁPIDAS ===
CACHE_RESPOSTAS = {
    "oi": "Oi! Tô aqui pra te ajudar! :heart:",
    "tudo bem": "Tô ótima, e tu? :smile:",
    "quem é você": "Sou Alice, sua IA fofa e rápida! :robot:",
    "obrigado": "De boa, amor! :heart_eyes:",
    "tchau": "Tchau, volta sempre! :wave:",
    "oq sobra para o betinha?": "SOBROU NADA KKKKKKKKKKKKKKKKKKKKKKKK <:Felipus:1419808523445076119>"
}

# === VARIAÇÕES AUTOMÁTICAS PARA CACHE INTELIGENTE ===
VARIACOES_AUTOMATICAS = {
    "oi": ["oie", "oii", "oii", "ola", "olá", "eai", "eaí", "opa"],
    "tudo bem": ["td bem", "tudo bom", "tudo", "tudo bem?", "tdb", "como vai", "como esta", "como tá"],
    "obrigado": ["obrigada", "brigado", "brigada", "valeu", "vlw", "obg", "obgd"],
    "tchau": ["flw", "ate mais", "até mais", "ate logo", "xau"]
}

# === CONVERTE :emoji: E PALAVRAS EM EMOJIS REAIS ===
def aplicar_estilo(texto):
    # Dicionário de emojis reais (para Discord) - REDUZIDO
    emoji_map = {
        'smile': '😊', 'heart': '❤️', 'sparkles': '✨', 'fire': '🔥',
        'robot': '🤖', 'bulb': '💡', 'star': '⭐', 'thumbsup': '👍',
        'clap': '👏', 'rocket': '🚀'
    }

    # Substitui nomes por emojis APENAS se estiverem entre :
    for nome, emoji in emoji_map.items():
        texto = texto.replace(f':{nome}:', emoji)

    # Remove emojis soltos no meio do texto
    palavras = texto.split()
    texto_limpo = []
    
    for palavra in palavras:
        # Se a palavra for só um :emoji: solto, aplica regras
        if palavra.strip(':') in emoji_map:
            texto_limpo.append(palavra)
        else:
            texto_limpo.append(palavra)
    
    texto = ' '.join(texto_limpo)

    # Adiciona emoji aleatório APENAS no final e com menos frequência
    estilo = personalidade['estilo_escrita']
    freq_emojis = estilo.get('frequencia_emojis', 0.3)  # Padrão 30%
    
    if estilo.get('usa_emojis', True) and random.random() < freq_emojis:
        # Só adiciona se não tiver muitos emojis já
        emoji_count = sum(1 for char in texto if char in ['😊', '❤️', '✨', '🔥', '🤖', '💡', '⭐', '👍', '👏', '🚀'])
        if emoji_count <= 2:  # Máximo 2 emojis
            emojis_finais = ['😊', '❤️', '✨', '🔥', '🤖']
            texto += " " + random.choice(emojis_finais)

    # Gírias no final (mais controlado)
    if 'gírias' in estilo and estilo['gírias'] and random.random() < 0.3:
        g = random.choice(estilo['gírias'])
        if texto.endswith('?'):
            texto = texto[:-1] + f', {g}?'
        elif texto.endswith('.'):
            texto = texto[:-1] + f', {g}.'
        else:
            texto += f', {g}!'

    return texto

# === CACHE INTELIGENTE ===
def buscar_no_cache_inteligente(pergunta):
    pergunta_lower = pergunta.lower().strip()
    
    # 1. Match exato (rápido)
    if pergunta_lower in CACHE_RESPOSTAS:
        return CACHE_RESPOSTAS[pergunta_lower]
    
    # 2. Remove pontuação
    pergunta_limpa = re.sub(r'[?!.,;]', '', pergunta_lower)
    
    # 3. Busca por palavras-chave principais
    palavras_pergunta = pergunta_limpa.split()
    
    for chave_principal in CACHE_RESPOSTAS.keys():
        # Se a chave principal estiver na pergunta
        if chave_principal in pergunta_limpa:
            return CACHE_RESPOSTAS[chave_principal]
        
        # Busca nas variações automáticas
        if chave_principal in VARIACOES_AUTOMATICAS:
            for variacao in VARIACOES_AUTOMATICAS[chave_principal]:
                if variacao in pergunta_limpa:
                    return CACHE_RESPOSTAS[chave_principal]
    
    # 4. Busca por similaridade (bônus)
    for chave_principal in CACHE_RESPOSTAS.keys():
        palavras_chave = set(chave_principal.split())
        palavras_comuns = palavras_chave.intersection(set(palavras_pergunta))
        
        if len(palavras_comuns) >= 1:  # Pelo menos 1 palavra em comum
            return CACHE_RESPOSTAS[chave_principal]
    
    return None

# === BUSCA GOOGLE (SEM DELAY) ===
def buscar_google(pergunta):
    try:
        query = pergunta.replace(' ', '+')
        url = f"https://www.google.com/search?q={query}&hl=pt-BR&num=1"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(r.text, 'html.parser')
        link = soup.find('a', href=re.compile(r'^/url\?q='))
        if link:
            url_real = re.findall(r'q=(.*?)&', link['href'])[0]
            titulo = link.find('h3')
            titulo = titulo.get_text() if titulo else "Fonte"
            return f"[{titulo}]({url_real})"
    except:
        pass
    return ""

# === EVENTOS ===
@client.event
async def on_ready():
    print(f"{aplicar_estilo(personalidade['frases_fixas']['saudacao'])}")
    print(f"ALICE IA ONLINE: {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.strip()
    user_id = str(message.author.id)

    # DEBUG: Verificar se o usuário está no histórico
    print(f"DEBUG: User ID: {user_id}")
    print(f"DEBUG: Histórico keys: {list(historico.keys())}")
    print(f"DEBUG: User no histórico: {user_id in historico}")

    # === COMANDOS COM PREFIXO ===
    if content.startswith('!'):
        cmd = content.split()[0][1:].lower()
        if cmd == 'ping':
            await message.reply("pong! :ping_pong:")
            return
        if cmd == 'ajuda':
            await message.reply(
                "**Comandos:**\n`!ping` → pong\n`!info` → sobre mim\n`!limpar` → apaga histórico\n`!historico` → mostra seu histórico")
            return
        if cmd == 'info':
            await message.reply(f"Eu sou **{personalidade['nome']}**, {personalidade['personalidade']} :heart:")
            return
        if cmd == 'limpar':
            if user_id in historico:
                del historico[user_id]
            await message.reply("Histórico limpo! :broom:")
            return
        if cmd == 'historico':
            if user_id in historico:
                total_msgs = len(historico[user_id])
                # Mostra as últimas 3 mensagens do histórico
                ultimas = historico[user_id][-3:] if total_msgs >= 3 else historico[user_id]
                historico_texto = ""
                for msg in ultimas:
                    role = "👤" if msg['role'] == 'user' else "🤖"
                    content_short = msg['content'][:50] + "..." if len(msg['content']) > 50 else msg['content']
                    historico_texto += f"{role} {content_short}\n"

                await message.reply(f"**Seu histórico:** {total_msgs} mensagens\n\n{historico_texto}")
            else:
                await message.reply("Você não tem histórico ainda.")
            return

    # === IA SÓ COM MENÇÃO ===
    if client.user not in message.mentions:
        return

    pergunta = content.replace(f'<@{client.user.id}>', '').strip()
    pergunta_lower = pergunta.lower()

    # === RESPOSTA INSTANTÂNEA (CACHE INTELIGENTE) ===
    resposta_cache = buscar_no_cache_inteligente(pergunta)
    if resposta_cache:
        await message.reply(aplicar_estilo(resposta_cache))
        return

    # === SAUDAÇÃO VAZIA ===
    if not pergunta:
        await message.reply(aplicar_estilo(personalidade['frases_fixas']['saudacao']))
        return

    async with message.channel.typing():
        # === HISTÓRICO ===
        msgs = historico.get(user_id, [])
        print(f"DEBUG: Mensagens carregadas para user {user_id}: {len(msgs)}")  # DEBUG

        msgs.append({'role': 'user', 'content': pergunta})

        # === BUSCA ===
        contexto = ""
        if any(p in pergunta_lower for p in PALAVRAS_BUSCA):
            contexto = buscar_google(pergunta)
            if contexto:
                msgs.append({'role': 'system', 'content': f"Contexto: {contexto}"})

        # === PREPARA MENSAGENS PARA O OLLAMA ===
        mensagens_ollama = []

        # Adiciona a personalidade como system message (FORÇADA)
        estilo = personalidade['estilo_escrita']
        gírias_texto = ', '.join(estilo['gírias']) if 'gírias' in estilo else 'mano, tipo'

        mensagens_ollama.append({
            'role': 'system',
            'content': f"""Você é {personalidade['nome']}, {personalidade['personalidade']}.
Tom: {personalidade['tom']}. 
Características: Conversa natural, às vezes usa emojis, fala descontraída.

REGRAS IMPORTANTES:
1. Fale como uma pessoa real, não como um assistente
2. Use português correto, mas descontraído
3. Emojis apenas no final das frases quando fizer sentido
4. Seja direta e evite repetições
5. Responda de forma coesa e natural
6. Máximo 2 frases por resposta

Gírias ocasionais: {gírias_texto}

NUNCA diga que é uma IA ou modelo de linguagem."""
        })

        # Adiciona o histórico de conversa (últimas 6 mensagens)
        for msg in msgs[-6:]:
            mensagens_ollama.append(msg)

        # Adiciona contexto de busca se houver
        if contexto:
            mensagens_ollama.append({'role': 'system', 'content': f"Contexto adicional: {contexto}"})

        print(f"DEBUG: Enviando para Ollama: {len(mensagens_ollama)} mensagens")
        for msg in mensagens_ollama:
            role = msg['role']
            content_preview = msg['content'][:80] + "..." if len(msg['content']) > 80 else msg['content']
            print(f"DEBUG: {role}: {content_preview}")

        try:
            resposta = ollama.chat(
                model=MODEL,
                messages=mensagens_ollama,
                options={'num_predict': 150, 'temperature': 0.7}  # Otimizado para velocidade
            )
            texto = resposta['message']['content'].strip()
            texto = aplicar_estilo(texto)
            print(f"DEBUG: Resposta crua: {texto}")
        except Exception as e:
            print(f"Erro Ollama: {e}")
            texto = aplicar_estilo(personalidade['frases_fixas']['erro'])

        # === SALVA HISTÓRICO ===
        msgs.append({'role': 'assistant', 'content': texto})
        historico[user_id] = msgs[-10:]  # Mantém apenas as últimas 10 mensagens
        print(f"DEBUG: Histórico atualizado - User {user_id}: {len(historico[user_id])} mensagens")  # DEBUG

        await message.reply(f"{texto}\n\n{contexto}" if contexto else texto)

# === SALVAR HISTÓRICO ===
def salvar_historico():
    try:
        print(f"DEBUG: Salvando histórico com {len(historico)} usuários")  # DEBUG
        for user_id, msgs in historico.items():
            print(f"DEBUG: Salvando user {user_id}: {len(msgs)} mensagens")

        with open(caminho_historico, 'w', encoding='utf-8') as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)
        print(f"\nHistórico salvo: {len(historico)} usuários")
        print(aplicar_estilo(personalidade['frases_fixas']['despedida']))
    except Exception as e:
        print(f"Erro ao salvar histórico: {e}")

atexit.register(salvar_historico)

# === INICIA ===
print("Iniciando Alice IA...")
client.run(TOKEN)