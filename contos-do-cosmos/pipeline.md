# Como um reel é feito

1. **Roteiro**: escolher uma curiosidade, escrever no formato de [formato.md](formato.md) e conferir a ciência com o livro.
2. **Arte**: se precisar de algo novo, gerar no Gemini com `gemini_art.py` (estilo "toy/clay 3D"). Sprites saem em fundo magenta e são recortados (`arte/<nome>_cut.png`); cenários saem em 9:16 (`arte/<nome>.png`). Cada imagem custa alguns centavos de dólar (11 imagens ≈ US$ 0,45–0,80).
3. **Episódio no código**: um item novo em `EPISODES` no `universo.py`, com as cenas (desenho, fala, zoom/foco da câmera, palavras que pulam na tela). Helpers prontos: `note_pill`, `ticking_clock`, `glow_ball`, `flash`, `anti()`, `ask_comment()`.
4. **Render no servidor**: copiar `universo.py`, `reel.py`, `campaigns.py` e `formatting.py` pra uma pasta e rodar `python universo.py <n> <saida>` (≈1,5 min por reel).
5. **Checagem de voz**: `python ouvir_narracao.py <narracao.mp3>`. O Gemini transcreve e marca palavras com sotaque espanhol ou embaralhadas; reescrever e renderizar de novo se aparecer alguma.
6. **Aprovação**: você assiste (fora do player do chat, que fica sem som) e aprova.
7. **Fila**: o arquivo entra em `/opt/promobot/contos_queue` com o título; o bot posta às 19h no Instagram e no YouTube, deixa rascunho no TikTok e manda a legenda no Telegram.

## Contas e acesso

- Instagram: testador no app da Meta "Make Barata Bot", com token próprio.
- YouTube: mesmo app OAuth do Google (auditoria aprovada, uploads públicos). Reautenticar com `python youtube.py login contos`.
- TikTok: segunda conta de teste do app "Make Barata Bot". Reautenticar com `python tiktok.py link` e `python tiktok.py code <code> contos` no servidor.
