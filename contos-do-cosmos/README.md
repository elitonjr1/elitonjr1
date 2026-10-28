# Contos do Cosmos

Reels curtos (≈60 s, vertical 9:16) com curiosidades do livro **Uma Breve História do Tempo**, de Stephen Hawking, contadas como histórias, em português.

| Plataforma | Conta | Como posta |
|---|---|---|
| Instagram | @contosdocosmos | automático, público |
| YouTube | Contos do Cosmos (@contos.docosmos) | automático, público, Shorts, categoria Educação |
| TikTok | @contos.do.cosmos | automático como **rascunho**: você toca em Publicar; a legenda chega no Telegram (Mensagens Salvas) pra colar |

O bot posta **todo dia às 19h** a próxima peça da fila.

## Onde as coisas estão

O código está em [codigo/](codigo/) (motor dos vídeos, arte 3D, checagem de voz, bot de postagem e metadados da fila), copiado do servidor do bot em 28/10/2026. Os vídeos (.mp4) não entram no repositório.

No servidor do bot: cópia em uso em `/opt/promobot/universo`, fila em `/opt/promobot/contos_queue`, versões antigas em `/opt/promobot/contos_old_versions` e `/opt/promobot/contos_2d_antigos`.

Os segredos (`.env`, tokens) **nunca** entram neste repositório.

## Arquivos

- [codigo/](codigo/): o código e a arte.
- [formato.md](formato.md): estrutura de roteiro, estilo visual, voz e regras combinadas.
- [episodios.md](episodios.md): reels feitos, fila e lista de curiosidades que ainda faltam.
- [pipeline.md](pipeline.md): como um reel é feito, do roteiro ao post.
- [proximos-passos.md](proximos-passos.md): o que vem agora.
