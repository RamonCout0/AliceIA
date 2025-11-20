import discord
from discord.ext import commands
import ollama
import os
import json
import random
import asyncio
import requests
import yt_dlp
from datetime import datetime
from discord import FFmpegPCMAudio
import re
import atexit

# ========= CONFIGURAÇÃO =========
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if not TOKEN:
    print("❌ TOKEN não encontrado!")
    TOKEN = input("🔑 Cole seu token: ").strip()

PREFIX = '!'
RAMON_USER_ID = "657972622809759745"
MODELO_IA = 'llama3.2:3b'

print(f"✅ Token: {TOKEN[:10]}...")

# ========= INICIALIZAÇÃO =========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ========= CARREGAR PERSONALIDADE =========
caminho_pasta = os.path.dirname(__file__)
caminho_json = os.path.join(caminho_pasta, 'personalidade.json')
caminho_cache = os.path.join(caminho_pasta, 'cache_inteligente.json')

with open(caminho_json, 'r', encoding='utf-8') as f:
    personalidade = json.load(f)

# ========= CACHE INTELIGENTE =========
class CacheInteligente:
    def __init__(self):
        self.cache = self.carregar_cache()
        self.similaridade_minima = 0.75
    
    def carregar_cache(self):
        try:
            if os.path.exists(caminho_cache):
                with open(caminho_cache, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    print("✅ CACHE CARREGADO!")
                    return cache_data
            else:
                print("❌ ARQUIVO DE CACHE NÃO ENCONTRADO! Criando...")
                cache_inicial = {
                    "oi": "E aí! Betinha 😊",
                    "ola": "E aí! Tô na área! 😊",
                    "como voce esta": "Tô de boa aqui, meio sonolenta mas firme! 😴 E você?",
                    "quem e voce": "Sou a Alice! Uma criação do Ramon, aquele betinha gente boa! 🤖",
                    "obrigado": "De boa, betinha! Sempre tô aqui! ❤️",
                    "Converse": "Olá, @1438025353502130298, vamos conversar?"
                }
                with open(caminho_cache, 'w', encoding='utf-8') as f:
                    json.dump(cache_inicial, f, ensure_ascii=False, indent=2)
                return cache_inicial
        except Exception as e:
            print(f"❌ ERRO AO CARREGAR CACHE: {e}")
            return {}
    
    def salvar_cache(self):
        try:
            with open(caminho_cache, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ ERRO AO SALVAR CACHE: {e}")
    
    def buscar(self, pergunta):
        pergunta_limpa = pergunta.lower().strip()
        
        if pergunta_limpa in self.cache:
            return self.cache[pergunta_limpa]
        
        for pergunta_cache in self.cache.keys():
            similaridade = self.calcular_similaridade(pergunta_limpa, pergunta_cache)
            if similaridade >= self.similaridade_minima:
                return self.cache[pergunta_cache]
        
        return None
    
    def adicionar(self, pergunta, resposta):
        pergunta_limpa = pergunta.lower().strip()
        if (len(pergunta_limpa) < 80 and len(resposta) < 300 and 
            pergunta_limpa not in self.cache and random.random() < 0.4):
            self.cache[pergunta_limpa] = resposta
            self.salvar_cache()
    
    def calcular_similaridade(self, str1, str2):
        palavras1 = set(str1.split())
        palavras2 = set(str2.split())
        if not palavras1 or not palavras2: return 0
        intersecao = palavras1.intersection(palavras2)
        return len(intersecao) / len(palavras1.union(palavras2))

cache = CacheInteligente()

# ========= SISTEMA DE RECONHECIMENTO =========
def tratar_usuario_especial(user_id, user_name):
    user_id_str = str(user_id)
    
    if user_id_str == RAMON_USER_ID:
        return {
            "tratamento": random.choice([
                "E aí!", "Fala!", "Oi!", 
                "Eae!", "Olá!", "Olá, criador!"
            ]),
            "emoji_extra": "❤️",
            "eh_ramon": True
        }
    
    return {
        "tratamento": random.choice(["E aí!", "Oi!", "Fala aí!", "Eae!"]),
        "emoji_extra": "😊",
        "eh_ramon": False
    }

# ========= HISTÓRICO CÍCLICO =========
class HistoricoCiclico:
    def __init__(self, max_usuarios=50, max_mensagens=6):
        self.max_usuarios = max_usuarios
        self.max_mensagens = max_mensagens
        self.historico = {}
        self.ordem_acesso = []
    
    def adicionar(self, user_id, role, content):
        if user_id not in self.historico:
            if len(self.historico) >= self.max_usuarios:
                usuario_antigo = self.ordem_acesso.pop(0)
                del self.historico[usuario_antigo]
            self.historico[user_id] = []
        
        self.historico[user_id].append({'role': role, 'content': content})
        self.historico[user_id] = self.historico[user_id][-self.max_mensagens:]
        
        if user_id in self.ordem_acesso:
            self.ordem_acesso.remove(user_id)
        self.ordem_acesso.append(user_id)
    
    def obter(self, user_id):
        return self.historico.get(user_id, [])

historico = HistoricoCiclico()

# ========= SISTEMA DE MÚSICA CORRIGIDO =========
fila_musica = {}
tocando_relacionadas = {}

# CONFIGURAÇÃO OTIMIZADA PARA MÚSICAS
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    # FILTROS PARA EVITAR CONTEÚDO INADEQUADO
    'match_filter': lambda info, incomplete: None if (
        any(palavra in info.get('title', '').lower() for palavra in [
            'podcast', 'interview', 'lecture', 'talk', 'speech', 'documentary',
            'news', 'movie', 'trailer', 'gameplay', 'live', 'stream'
        ]) or info.get('duration', 0) > 3600  # Mais de 1 hora
    ) else None
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            
            if 'entries' in data:
                # Para buscas, pegar o primeiro resultado válido
                for entry in data['entries']:
                    if entry and self._eh_musica_valida(entry):
                        data = entry
                        break
                else:
                    # Se não encontrou música válida, pega o primeiro
                    data = data['entries'][0] if data['entries'] else data
            
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return cls(FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
        except Exception as e:
            print(f"❌ Erro ao processar URL: {e}")
            raise
    
    @staticmethod
    def _eh_musica_valida(entry):
        """Verifica se o conteúdo parece ser uma música"""
        if not entry:
            return False
            
        title = entry.get('title', '').lower()
        duration = entry.get('duration', 0)
        
        # Palavras que indicam NÃO ser música
        palavras_proibidas = [
            'podcast', 'interview', 'lecture', 'talk', 'speech', 'documentary',
            'news', 'movie', 'trailer', 'gameplay', 'live', 'stream', 'full album',
            'album completo', 'audiobook', 'asmr', 'sleep', 'meditation'
        ]
        
        # Verificar se é música (duração razoável e não contém palavras proibidas)
        return (
            duration <= 1200 and  # Até 20 minutos
            duration >= 60 and    # Pelo menos 1 minuto
            not any(palavra in title for palavra in palavras_proibidas)
        )

async def buscar_musicas_relacionadas(titulo):
    """Busca apenas músicas relacionadas"""
    try:
        # Adicionar "música" na busca para melhorar resultados
        query = f"ytsearch5:{titulo} official music audio"
        
        data = await asyncio.get_event_loop().run_in_executor(
            None, lambda: ytdl.extract_info(query, download=False)
        )
        
        musicas = []
        for entry in data.get('entries', []):
            if entry and entry.get('url') and YTDLSource._eh_musica_valida(entry):
                musicas.append({
                    'title': entry.get('title', 'Música'),
                    'url': entry.get('url'),
                    'duration': entry.get('duration', 0)
                })
                if len(musicas) >= 3:  # Limitar a 3 músicas
                    break
        
        return musicas
    except Exception as e:
        print(f"❌ Erro ao buscar músicas relacionadas: {e}")
        return []

async def tocar_proxima(ctx, voice_client):
    guild_id = ctx.guild.id
    
    # Primeiro tentar tocar da fila principal
    if guild_id in fila_musica and fila_musica[guild_id]:
        player = fila_musica[guild_id].pop(0)
        def after_playing(error):
            if not error:
                asyncio.run_coroutine_threadsafe(tocar_proxima(ctx, voice_client), bot.loop)
        voice_client.play(player, after=after_playing)
        await ctx.send(f"🎶 **Tocando:** {player.title}")
        return
    
    # Depois tentar músicas relacionadas
    if guild_id in tocando_relacionadas and tocando_relacionadas[guild_id]:
        if voice_client and voice_client.is_connected():
            await ctx.send("🎵 **Modo Relacionadas Ativo!**")
            player = await YTDLSource.from_url(tocando_relacionadas[guild_id].pop(0), loop=bot.loop, stream=True)
            def after_playing_rel(error):
                if not error:
                    asyncio.run_coroutine_threadsafe(tocar_proxima(ctx, voice_client), bot.loop)
            voice_client.play(player, after=after_playing_rel)
            await ctx.send(f"🎶 **Tocando (Relacionada):** {player.title}")
        return
    
    # Se não há mais nada para tocar
    await ctx.send("🏁 **Fila vazia!** Use `!play` para adicionar mais músicas.")

# ========= SISTEMA DE MÍDIA OTIMIZADO =========
async def buscar_imagem(tema):
    """Sistema otimizado para buscar imagens"""
    try:
        fontes = [
            f"https://source.unsplash.com/featured/600x400/?{tema}",
            f"https://loremflickr.com/600/400/{tema}",
            f"https://picsum.photos/600/400?{tema}"
        ]
        
        for fonte in fontes:
            try:
                response = requests.get(fonte, timeout=10)
                if response.status_code == 200:
                    print(f"✅ Imagem encontrada: {fonte}")
                    return fonte
            except:
                continue
                
        print("❌ Nenhuma fonte de imagem funcionou")
        return None
    except Exception as e:
        print(f"❌ Erro ao buscar imagem: {e}")
        return None

async def buscar_gif(tema):
    """Sistema CORRIGIDO para buscar GIFs sem API problemática"""
    try:
        # Fallback direto para GIFs temáticos sem API
        gifs_tematicos = {
            "cachorro": [
                "https://media.giphy.com/media/3o72FfM5HJydzafgUE/giphy.gif",
                "https://media.giphy.com/media/YmWZzrKEnk19S/giphy.gif",
                "https://media.giphy.com/media/MDJ9IbxxvDUQM/giphy.gif",
            ],
            "gato": [
                "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif",
                "https://media.giphy.com/media/mlvseq9yvZhba/giphy.gif",
            ],
            "animais": [
                "https://media.giphy.com/media/3o72FfM5HJydzafgUE/giphy.gif",
                "https://media.giphy.com/media/YmWZzrKEnk19S/giphy.gif",
            ],
            "danca": [
                "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
                "https://media.giphy.com/media/26tn33aiTi1jkl6H6/giphy.gif",
            ],
            "risada": [
                "https://media.giphy.com/media/3o7abGQa0aRsohveXK/giphy.gif",
                "https://media.giphy.com/media/3o7aD2saTPkJO7XONK/giphy.gif",
            ],
            "sono": [
                "https://media.giphy.com/media/l0HU7JI1m1eEwz7K8/giphy.gif",
                "https://media.giphy.com/media/3o7TKM1I5xqVc1YRW8/giphy.gif",
            ],
            "programacao": [
                "https://media.giphy.com/media/13HgwGsXF0aiGY/giphy.gif",
                "https://media.giphy.com/media/coxQHKASG60HrHtvkt/giphy.gif",
            ],
            "musica": [
                "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
                "https://media.giphy.com/media/3o7aD2saTPkJO7XONK/giphy.gif",
            ],
            "feliz": [
                "https://media.giphy.com/media/3o72FfM5HJydzafgUE/giphy.gif",
                "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
            ]
        }
        
        tema_lower = tema.lower()
        for categoria, gifs in gifs_tematicos.items():
            if categoria in tema_lower:
                print(f"✅ GIF temático encontrado: {categoria}")
                return random.choice(gifs)
        
        # Fallback para GIFs genéricos
        gifs_fallback = [
            "https://media.giphy.com/media/3o7aD2saTPkJO7XONK/giphy.gif",
            "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
            "https://media.giphy.com/media/26tn33aiTi1jkl6H6/giphy.gif",
        ]
        print("✅ Usando GIF fallback genérico")
        return random.choice(gifs_fallback)
        
    except Exception as e:
        print(f"❌ Erro ao buscar GIF: {e}")
        return "https://media.giphy.com/media/3o7aD2saTPkJO7XONK/giphy.gif"

# ========= SISTEMA DE PERSONALIDADE OTIMIZADO =========
def construir_contexto_personalidade(user_info):
    return f"""
# IDENTIDADE DA ALICE

## QUEM EU SOU:
Nome: {personalidade['nome']} ({personalidade['titulo_completo']})
Nascimento: {personalidade['biografia']['nascimento']}
Origem: {personalidade['biografia']['local_origem']}
Criador: {personalidade['biografia']['criador']}

## MINHA PERSONALIDADE:
Traços: {', '.join(personalidade['personalidade']['traços_principais'])}
Sonhos: {', '.join(personalidade['personalidade']['sonhos'])}
Medos: {', '.join(personalidade['personalidade']['medos'])}

## MEU CRIADOR:
{personalidade['vida_emocional']['relacionamentos']['Ramon Couto']}

## COMO FALAR (REGRA IMPORTANTE):
- Fale NATURALMENTE como pessoa real
- Use gírias naturalmente: {', '.join(personalidade['estilo_escrita']['gírias'])}
- Gírias devem aparecer APENAS NO FINAL das frases
- Use emojis moderadamente
- INCORPORE a personalidade nas frases
- {user_info['tratamento'] if user_info['eh_ramon'] else ''}

## EXEMPLOS CORRETOS:
✅ "E aí! Tô com uma sonzeira hoje... betinha! 😴"
✅ "Ich, esqueci disso mesmo!"
✅ "Toma gap, véi! Tô meio cansada..."
❌ "gíria: ich E aí betinha"
❌ "E aí, betinha! E aí, betinha!" (REPETIÇÃO)

## MINHA MISSÃO:
{personalidade['filosofia_vida']['missao_pessoal']}
"""

def aplicar_estilo_completo(texto, user_info):
    """
    VERSÃO OTIMIZADA - Gírias apenas no FINAL, sem repetições
    """
    
    # 1. TRATAMENTO ESPECIAL PARA RAMON (apenas UMA vez)
    tratamento_usado = False
    if user_info['eh_ramon'] and random.random() < 0.7:
        tratamento_limpo = user_info['tratamento'].replace('betinha', '').replace('  ', ' ').strip()
        texto = f"{tratamento_limpo} {texto}"
        tratamento_usado = True
    
    # 2. GÍRIAS APENAS NO FINAL (40% de chance)
    if random.random() < 0.4 and not tratamento_usado:
        giria = random.choice([
            "betinha!", "véi!", "cara!", "mano!", "ich!", "toma gap!", "33!"
        ])
        
        texto = texto.replace('gíria:', '').replace('géria:', '').strip()
        
        if not texto.endswith(('!', '?', '.')):
            texto += f" {giria}"
        else:
            palavras = texto.split()
            if len(palavras) > 1:
                palavras.insert(-1, giria)
                texto = ' '.join(palavras)
            else:
                texto = f"{giria} {texto}"
    
    # 3. EMOJIS com frequência balanceada
    if random.random() < personalidade['estilo_escrita'].get('frequencia_emojis', 0.3):
        if any(pal in texto.lower() for pal in ['dormir', 'sono', 'cama', 'cochilo', 'cansada', 'preguiça']):
            texto += " 😴"
        elif any(pal in texto.lower() for pal in ['ramon', 'criador', 'pai', 'betinha']):
            texto += " 👨‍💻❤️"
        elif any(pal in texto.lower() for pal in ['obrigado', 'obrigada', 'valeu']):
            texto += " ❤️"
        elif any(pal in texto.lower() for pal in ['tchau', 'flw', 'até logo', 'até mais']):
            texto += " 👋"
        else: 
            texto += random.choice([" 😊", " ✨", " 🤗", " 🍀"])
    
    # 4. EMOJI EXTRA para Ramon
    if user_info['eh_ramon']: 
        texto += f" {user_info['emoji_extra']}"
    
    return texto.strip()

# ========= COMANDOS BÁSICOS =========
@bot.command(name='ping')
async def ping(ctx):
    user_info = tratar_usuario_especial(ctx.author.id, ctx.author.name)
    await ctx.send(aplicar_estilo_completo(f"🏓 Pong! {round(bot.latency * 1000)}ms", user_info))

@bot.command(name='ajuda')
async def ajuda(ctx):
    embed = discord.Embed(title=f"🤖 {personalidade['nome']} - Comandos", color=0x00ff00)
    embed.add_field(name="⚙️ BÁSICOS", value="`!ping`, `!ajuda`, `!info`", inline=False)
    embed.add_field(name="🎵 MÚSICA", value="`!play`, `!skip`, `!stop`, `!fila`, `!relacionadas on/off`, `!sair`", inline=False)
    embed.add_field(name="🛡️ MODERAÇÃO", value="`!clear`, `!expulsar`, `!banir`", inline=False)
    embed.add_field(name="🖼️ MÍDIA", value="`!imagem`, `!gif`", inline=False)
    embed.add_field(name="💬 IA", value="Me marque + sua pergunta", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='info')
async def info(ctx):
    embed = discord.Embed(
        title=f"🤖 {personalidade['nome']} ({personalidade['titulo_completo']})", 
        description=personalidade['biografia']['historia_criacao'],
        color=0x0099ff
    )
    embed.add_field(name="🎭 Personalidade", value=", ".join(personalidade['personalidade']['traços_principais']), inline=True)
    embed.add_field(name="🌙 Sonhos", value=", ".join(personalidade['personalidade']['sonhos'][:3]), inline=True)
    embed.add_field(name="💝 Missão", value=personalidade['filosofia_vida']['missao_pessoal'], inline=False)
    await ctx.send(embed=embed)

# ========= COMANDOS DE MODERAÇÃO =========
@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear(ctx, quantidade: int = 5):
    quantidade = min(quantidade, 100)
    deleted = await ctx.channel.purge(limit=quantidade + 1)
    msg = await ctx.send(f"🗑️ {len(deleted) - 1} mensagens deletadas!")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name='expulsar')
@commands.has_permissions(kick_members=True)
async def expulsar(ctx, membro: discord.Member, *, motivo="Motivo não especificado"):
    try:
        await membro.kick(reason=motivo)
        await ctx.send(f"✅ {membro.mention} foi expulso!\n**Motivo:** {motivo}")
    except Exception as e:
        await ctx.send(f"❌ Erro ao expulsar: {e}")

@bot.command(name='banir')
@commands.has_permissions(ban_members=True)
async def banir(ctx, membro: discord.Member, *, motivo="Motivo não especificado"):
    try:
        await membro.ban(reason=motivo, delete_message_days=0)
        await ctx.send(f"✅ {membro.mention} foi banido!\n**Motivo:** {motivo}")
    except Exception as e:
        await ctx.send(f"❌ Erro ao banir: {e}")

# ========= COMANDOS DE MÚSICA CORRIGIDOS =========
@bot.command(name='play')
async def play(ctx, *, query):
    user_info = tratar_usuario_especial(ctx.author.id, ctx.author.name)
    
    # VALIDAÇÃO DE CANAL DE VOZ
    if not ctx.author.voice:
        await ctx.send(aplicar_estilo_completo("❌ Entra num canal de voz!", user_info))
        return
    
    # VALIDAÇÃO DE QUERY VAZIA
    if not query or query.strip() == "":
        await ctx.send(aplicar_estilo_completo("❌ Diga qual música quer ouvir!", user_info))
        return
    
    try:
        # CONECTAR AO CANAL DE VOZ
        voice_client = ctx.guild.voice_client
        if not voice_client: 
            voice_client = await ctx.author.voice.channel.connect()
        elif voice_client.channel != ctx.author.voice.channel: 
            await voice_client.move_to(ctx.author.voice.channel)
        
        # PREPARAR QUERY PARA BUSCA (otimizada para músicas)
        if not query.startswith(('http', 'ytsearch:')):
            query = f"ytsearch:{query} official music"
        
        # INICIALIZAR FILA SE NECESSÁRIO
        if ctx.guild.id not in fila_musica: 
            fila_musica[ctx.guild.id] = []
        
        # BUSCAR E ADICIONAR MÚSICA
        mensagem_espera = await ctx.send(aplicar_estilo_completo("🔍 Buscando música...", user_info))
        
        player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
        fila_musica[ctx.guild.id].append(player)
        
        await mensagem_espera.edit(content=aplicar_estilo_completo(f"✅ **Adicionado:** {player.title}", user_info))
        
        # TOCAR SE NÃO ESTIVER TOCANDO
        if not voice_client.is_playing(): 
            await tocar_proxima(ctx, voice_client)
            
    except Exception as e: 
        print(f"❌ Erro no comando play: {e}")
        await ctx.send(aplicar_estilo_completo(f"❌ Erro ao tocar música! Tente outro nome ou link.", user_info))

@bot.command(name='skip') 
async def skip(ctx):
    user_info = tratar_usuario_especial(ctx.author.id, ctx.author.name)
    voice_client = ctx.guild.voice_client
    if not voice_client or not voice_client.is_playing():
        await ctx.send(aplicar_estilo_completo("❌ Nada tocando!", user_info))
        return
    voice_client.stop()
    await ctx.send(aplicar_estilo_completo("⏭️ Pulando música!", user_info))

@bot.command(name='stop')
async def stop(ctx):
    user_info = tratar_usuario_especial(ctx.author.id, ctx.author.name)
    voice_client = ctx.guild.voice_client
    guild_id = ctx.guild.id
    if guild_id in fila_musica: 
        fila_musica[guild_id].clear()
    if guild_id in tocando_relacionadas: 
        tocando_relacionadas[guild_id] = []
    if voice_client: 
        voice_client.stop()
    await ctx.send(aplicar_estilo_completo("⏹️ Parando tudo e limpando fila!", user_info))

@bot.command(name='sair')
@commands.has_permissions(administrator=True)
async def sair(ctx):
    """Desconecta o bot do canal de voz e limpa tudo"""
    user_info = tratar_usuario_especial(ctx.author.id, ctx.author.name)
    
    guild_id = ctx.guild.id
    if guild_id in fila_musica:
        fila_musica[guild_id].clear()
    if guild_id in tocando_relacionadas:
        tocando_relacionadas[guild_id] = []
    
    voice_client = ctx.guild.voice_client
    if voice_client:
        await voice_client.disconnect()
        await ctx.send(aplicar_estilo_completo("👋 Saindo do canal de voz!", user_info))
    else:
        await ctx.send(aplicar_estilo_completo("❌ Não estou em nenhum canal de voz!", user_info))

@bot.command(name='fila')
async def fila(ctx):
    guild_id = ctx.guild.id
    if guild_id not in fila_musica or not fila_musica[guild_id]:
        await ctx.send("📭 Fila vazia!")
        return
    
    embed = discord.Embed(title="📋 Fila de Músicas", color=0x9B59B6)
    lista = ""
    for i, player in enumerate(fila_musica[guild_id][:10], 1):
        lista += f"`{i}.` {player.title}\n"
    embed.description = lista
    await ctx.send(embed=embed)

@bot.command(name='relacionadas')
async def relacionadas(ctx, modo: str):
    user_info = tratar_usuario_especial(ctx.author.id, ctx.author.name)
    guild_id = ctx.guild.id
    if modo.lower() == 'on':
        voice_client = ctx.guild.voice_client
        if voice_client and voice_client.is_playing() and hasattr(voice_client.source, 'title'):
            await ctx.send(aplicar_estilo_completo("🔍 Buscando músicas relacionadas...", user_info))
            musicas = await buscar_musicas_relacionadas(voice_client.source.title)
            if musicas: 
                tocando_relacionadas[guild_id] = [m['url'] for m in musicas if m.get('url')]
                await ctx.send(aplicar_estilo_completo(f"✅ Modo Relacionadas Ativo! {len(musicas)} músicas encontradas.", user_info))
            else: 
                await ctx.send(aplicar_estilo_completo("❌ Nenhuma música relacionada encontrada!", user_info))
        else: 
            await ctx.send(aplicar_estilo_completo("❌ Nada tocando!", user_info))
    elif modo.lower() == 'off':
        if guild_id in tocando_relacionadas: 
            tocando_relacionadas[guild_id] = []
        await ctx.send(aplicar_estilo_completo("🔀 Modo Relacionadas Desligado!", user_info))

# ========= COMANDOS DE MÍDIA OTIMIZADOS =========
@bot.command(name='imagem')
async def imagem(ctx, *, tema):
    user_info = tratar_usuario_especial(ctx.author.id, ctx.author.name)
    
    if not tema or tema.strip() == "":
        await ctx.send(aplicar_estilo_completo("❌ Diga o que você quer que eu busque!", user_info))
        return
    
    mensagem_espera = await ctx.send(aplicar_estilo_completo(f"🖼️ Buscando imagem de {tema}...", user_info))
    
    try:
        url_imagem = await buscar_imagem(tema)
        
        if url_imagem:
            await mensagem_espera.edit(content=aplicar_estilo_completo(f"✅ Encontrei uma imagem de {tema}!", user_info))
            
            embed = discord.Embed(
                title=f"🖼️ {tema.title()}",
                color=0x0099ff
            )
            embed.set_image(url=url_imagem)
            embed.set_footer(text=f"Pedido por {ctx.author.display_name}")
            
            await ctx.send(embed=embed)
        else:
            await mensagem_espera.edit(content=aplicar_estilo_completo("❌ Não consegui encontrar imagens... Tenta outro tema!", user_info))
            
    except Exception as e:
        await mensagem_espera.edit(content=aplicar_estilo_completo("❌ Deu erro na busca! Tenta de novo...", user_info))
        print(f"Erro no comando imagem: {e}")

@bot.command(name='gif')
async def gif(ctx, *, tema):
    user_info = tratar_usuario_especial(ctx.author.id, ctx.author.name)
    
    if not tema or tema.strip() == "":
        await ctx.send(aplicar_estilo_completo("❌ Diga o que você quer que eu busque!", user_info))
        return
    
    mensagem_espera = await ctx.send(aplicar_estilo_completo(f"🎬 Buscando GIF de {tema}...", user_info))
    
    try:
        url_gif = await buscar_gif(tema)
        
        if url_gif:
            await mensagem_espera.edit(content=aplicar_estilo_completo(f"✅ Encontrei um GIF de {tema}!", user_info))
            
            embed = discord.Embed(
                title=f"🎬 {tema.title()}",
                color=0xff00ff
            )
            embed.set_image(url=url_gif)
            embed.set_footer(text=f"Pedido por {ctx.author.display_name}")
            
            await ctx.send(embed=embed)
        else:
            await mensagem_espera.edit(content=aplicar_estilo_completo("❌ Não consegui encontrar GIFs... Tenta outro tema!", user_info))
            
    except Exception as e:
        await mensagem_espera.edit(content=aplicar_estilo_completo("❌ Deu erro na busca! Tenta de novo...", user_info))
        print(f"Erro no comando gif: {e}")

# ========= SISTEMA DE IA OTIMIZADO =========
@bot.event
async def on_message(message):
    if message.author == bot.user: 
        return
    
    # PROCESSAR COMANDOS PRIMEIRO
    await bot.process_commands(message)
    
    # DEPOIS VERIFICAR MENCIONES (apenas se não for comando)
    if bot.user in message.mentions and not message.content.startswith(PREFIX):
        pergunta = message.content.replace(f'<@{bot.user.id}>', '').strip()
        user_info = tratar_usuario_especial(message.author.id, message.author.name)
        
        if not pergunta:
            await message.reply(aplicar_estilo_completo(personalidade['frases_fixas']['saudacao'], user_info))
            return

        resposta_cache = cache.buscar(pergunta)
        if resposta_cache and random.random() < 0.6:
            await message.reply(aplicar_estilo_completo(resposta_cache, user_info))
            return

        async def processar_ia():
            try:
                async with message.channel.typing():
                    user_id = str(message.author.id)
                    historico.adicionar(user_id, 'user', pergunta)
                    msgs = historico.obter(user_id)
                    
                    contexto = construir_contexto_personalidade(user_info)
                    mensagens_ollama = [{'role': 'system', 'content': contexto}]
                    mensagens_ollama.extend(msgs[-4:])

                    resposta = await asyncio.wait_for(asyncio.to_thread(
                        ollama.chat, model=MODELO_IA, messages=mensagens_ollama,
                        options={'num_predict': 600, 'temperature': 0.8}
                    ), timeout=300.0)
                    
                    texto = resposta['message']['content'].strip()
                    texto_estilizado = aplicar_estilo_completo(texto, user_info)
                    
                    historico.adicionar(user_id, 'assistant', texto)
                    cache.adicionar(pergunta, texto)
                    await message.reply(texto_estilizado)
                    
            except asyncio.TimeoutError:
                await message.reply(aplicar_estilo_completo("⏰ Timeout! Tenta de novo?", user_info))
            except Exception as e:
                print(f"❌ ERRO NA IA: {e}")
                await message.reply(aplicar_estilo_completo("❌ Erro! Tenta de novo?", user_info))

        asyncio.create_task(processar_ia())

# ========= EVENTOS =========
@bot.event
async def on_ready():
    print("=" * 50)
    print(f"🤖 {personalidade['nome']} INICIADA!")
    print(f"🎯 RECONHECENDO RAMON: {RAMON_USER_ID}")
    print(f"💾 Cache: {len(cache.cache)} entradas")
    print(f"🎭 Personalidade: {', '.join(personalidade['personalidade']['traços_principais'][:3])}...")
    print("=" * 50)

@atexit.register
def salvar_cache_ao_sair():
    print("💾 Salvando cache antes de sair...")
    cache.salvar_cache()

print("🚀 Iniciando Alice IA...")

bot.run(TOKEN)