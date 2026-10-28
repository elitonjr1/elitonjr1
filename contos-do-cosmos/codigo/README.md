# Código do Contos do Cosmos

Cópia do código que roda no servidor do bot (`/opt/promobot`) para gerar e postar os vídeos do
**Contos do Cosmos**. Os segredos (tokens, chaves) ficam só no `.env` do servidor e **não** estão aqui.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `universo.py` | O motor dos episódios: cada episódio é uma lista de cenas (desenho, narração, câmera, palavras que aparecem). Grava a narração, corta por cena e desenha quadro a quadro. |
| `gemini_art.py` | Gera a arte 3D (estilo "brinquedo de massinha") com o modelo de imagem do Gemini e recorta o fundo magenta dos sprites (`*_cut.png`). |
| `ouvir_narracao.py` | Manda a narração para o Gemini ouvir e apontar palavras que soaram espanholas, erradas ou emboladas. |
| `reel.py` | Funções compartilhadas de vídeo: voz (edge-tts), legendas estilo TikTok, efeitos sonoros, easing. Veio do bot Make Barata e o `universo.py` usa partes dele. |
| `campaigns.py`, `formatting.py` | Dependências do `reel.py` (fonte, quebra de texto, pronúncia etc.). |
| `contos.py` | Posta o próximo vídeo da fila no Instagram, no YouTube (Shorts) e manda como rascunho no TikTok (`post_next()`). |
| `instagram.py`, `youtube.py`, `tiktok.py` | Clientes de postagem usados pelo `contos.py` (conta `contos`). |
| `requirements.txt` | Pacotes Python do bot. |
| `arte/` | Cenários e sprites PNG. Os `*_cut.png` são os recortados que o vídeo usa, e os PNGs sem `_cut` são os originais gerados. |
| `fila/` | Metadados da fila de postagem (`<número>-<nome>.json`: legenda, título do YouTube, quadro da capa). `fila/posted/` são os já postados. Os `.mp4` não vêm para o repositório. |

## Como renderizar um episódio

```bash
pip install -r requirements.txt   # requests, python-dotenv, pillow, edge-tts (+ telethon, só do bot)
# precisa também de: ffmpeg no PATH e a fonte Montserrat (/usr/share/fonts/truetype/montserrat)
python universo.py <número do episódio> <pasta de saída> [voz] [velocidade]
# ex.: python universo.py 5 saida   ->  saida/episodio5.mp4
```

Gerar arte nova: `python gemini_art.py <nome> <proporção> "<prompt>"` → `arte/<nome>.png`.

No servidor, a fila fica em `contos_queue/` (vídeo `.mp4` + `.json` com o mesmo nome) e o bot chama
`contos.post_next()`.

## Variáveis de ambiente (`.env`, só os nomes)

- Arte e revisão: `GEMINI_API_KEY`
- Instagram: `CONTOS_INSTAGRAM_TOKEN`, `INSTAGRAM_PUBLIC_HOST`, `INSTAGRAM_SERVE_PORT`
- YouTube: `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `CONTOS_YOUTUBE_REFRESH_TOKEN`, `YOUTUBE_PRIVACY`
- TikTok: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `CONTOS_TIKTOK_REFRESH_TOKEN`, `TIKTOK_REDIRECT_URI`, `TIKTOK_MODE`

Os clientes de postagem também guardam o token mais novo em `*_token*.json` ao lado do código
(ignorados pelo `.gitignore`).
