# Verificação da implementação de Downloads

Verificado em 29/09/2026 (America/Sao_Paulo), sobre o clone do commit `d22cdbe`, com as alterações locais desta implementação.

- 36 testes do backend aprovados com a versão base do lockfile.
- Os mesmos 36 testes aprovados com a nightly `2026.9.27.232945.dev0`.
- TypeScript e build de produção do Vite aprovados.
- Atualização real instalada em ambiente separado e ativada após o teste do adaptador. Estado anterior `2026.07.04`, novo estado `2026.09.27.232945`.
- Download real do vídeo público curto `jNQXAC9IVRw` realizado em MP4 e MP3 pelo formulário da interface. MP4: 533.932 bytes, vídeo AV1 e áudio AAC. MP3: 457.389 bytes, áudio MP3. FFprobe confirmou os fluxos.
- Entrega HTTP dos dois arquivos retornou 200, com os tipos `video/mp4` e `audio/mpeg`. Os bytes recebidos foram idênticos aos arquivos produzidos.
- O vídeo de teste antigo `BaW_jenozKc` retornou indisponível pelo YouTube e foi exibido como falha na interface, sem arquivo para salvar.
- Na interface, foram verificados navegação Downloads, entrada por link, seleção MP3/MP4, resolução máxima, criação de tarefa, resultados prontos, estado sem canal conectado e rejeição de links externos.
- Os testes cobrem paginação de 51 uploads, verificação de propriedade dos vídeos selecionados, isolamento dos downloads por navegador, limites da fila, expiração e remoção de arquivos, reinício de tarefas, falhas de conversão, segredo da API remota, assinatura e expiração dos links, falha de atualização e rollback.
- Os testes de conversão geram mídia sintética e executam transferência HTTP local e FFmpeg reais, substituindo apenas a extração de metadados do YouTube.

Não houve login Google de uma conta real, download privado, publicação no YouTube, push no GitHub ou deploy na Vercel. As rotas de listagem OAuth do canal foram verificadas com o serviço simulado. A API do worker e o gateway foram testados em ambiente de teste; a hospedagem real precisa ser configurada conforme `downloads.md`. A imagem Docker não foi construída porque o daemon Docker está desligado neste computador.

A aplicação foi deixada disponível em `http://127.0.0.1:8011/downloads`, com atualização automática habilitada. Esse servidor é temporário; a forma normal de iniciar o aplicativo continua descrita no README.
# Integração publicada — 30/09/2026

- Produção: https://youtube-acervo-aio.vercel.app/downloads. Deploy `dpl_9abPMiGDW2F38SmGKGfak5ZRWQ6E`, estado READY.
- `/downloads` e `/api/downloads/status`: HTTP 200; modo companion. `/api/auth/accounts`: HTTP 200 usando a configuração Neon existente.
- 37 testes passaram e o build TypeScript/Vite passou.
- Transferência real pelo site de `jNQXAC9IVRw` em MP3 e MP4, confirmação local, preparação e entrega pelos botões Salvar verificadas. Arquivos salvos em Downloads do Windows e codecs verificados com FFprobe.
- Iniciador verificado ao reutilizar serviço existente e ao iniciar serviço novo na porta 8011. Atualização automática ativa a cada 24h enquanto aberto.
- Consulta/validação de seleção do canal coberta por testes, inclusive paginação acima de 50 vídeos e rejeição de vídeo externo. Não houve teste real de um canal autenticado nesta sessão; a sessão de produção usada estava sem conta conectada. Vídeos privados podem precisar de cookies locais autorizados.
- Corrigidos fallback de rotas SPA da Vercel e exclusão indevida do módulo `app/database` durante o empacotamento.

