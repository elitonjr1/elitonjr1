# Contos do Cosmos

Reels curtos (≈60 s, vertical 9:16) com curiosidades do livro **Uma Breve História do Tempo**, de Stephen Hawking, contadas como histórias, em português.

| Plataforma | Conta | Como posta |
|---|---|---|
| Instagram | @contosdocosmos | automático, público |
| YouTube | Contos do Cosmos (@contos.docosmos) | automático, público, Shorts, categoria Educação |
| TikTok | @contos.do.cosmos | automático como **rascunho**: você toca em Publicar; a legenda chega no Telegram (Mensagens Salvas) pra colar |

O bot posta **todo dia às 19h** a próxima peça da fila.

## Onde as coisas estão

Esta pasta guarda o conhecimento do projeto (formato, roteiros, decisões e plano). O código e os vídeos ainda **não** estão no repositório:

- **No seu PC**, na pasta de trabalho do Claude (`scratch-2026-10-18-acc354`): `universo/universo.py` (motor dos vídeos), `universo/gemini_art.py` (gera a arte 3D), `universo/ouvir_narracao.py` (checagem da voz), `universo/arte/` (sprites e cenários) e `preview/` (vídeos renderizados).
- **No servidor do bot**: cópia persistente em `/opt/promobot/universo`, fila em `/opt/promobot/contos_queue`, versões antigas em `/opt/promobot/contos_old_versions` e `/opt/promobot/contos_2d_antigos`. O bot (`contos.post_next`, `youtube.py`, `tiktok.py`) é o mesmo do Make Barata, com tokens próprios no `.env`.

Os segredos (`.env`, tokens) **nunca** entram neste repositório.

## Arquivos

- [formato.md](formato.md): estrutura de roteiro, estilo visual, voz e regras combinadas.
- [episodios.md](episodios.md): reels feitos, fila e lista de curiosidades que ainda faltam.
- [pipeline.md](pipeline.md): como um reel é feito, do roteiro ao post.
- [proximos-passos.md](proximos-passos.md): o que vem agora.
