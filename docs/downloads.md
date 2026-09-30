# Downloads MP3 e MP4

A ferramenta **Downloads** aceita links de vídeos, Shorts, `youtu.be` e IDs. Também permite escolher vídeos do canal conectado em Configurações. Os lotes e a fila não têm limite fixo de quantidade de vídeos. MP3 usa 192 kbps; MP4 inclui áudio e oferece limites de 360p, 720p e 1080p. A resolução real depende do que o YouTube disponibiliza. O aplicativo não baixa transmissões ainda ao vivo.

Os vídeos do canal são listados por OAuth usando a playlist de uploads e a YouTube Data API, incluindo vídeos que já têm descrição. A seleção é verificada novamente antes de enfileirar. Essa API retorna metadados, não o arquivo de mídia: o download usa o mesmo motor `yt-dlp` dos links. OAuth não é convertido em cookies nem enviado ao worker.

## Downloads por playlist

Em **Downloads → Por playlist**, escolha uma playlist do canal conectado ou cole um link/ID de playlist do YouTube e clique em **Carregar vídeos da playlist**. Uma conta conectada é necessária para consultar a API. Playlists públicas de outros canais também podem ser consultadas; playlists privadas dependem do acesso dessa conta.

Todos os vídeos consultáveis aparecem selecionados, na ordem da playlist. Desmarque exceções ou filtre por título. O aplicativo percorre todas as páginas, remove repetições e informa quantos vídeos não puderam ser consultados. Escolha MP3 ou MP4 e clique em Preparar. Consultar um vídeo na API não garante que o motor de download consiga baixar vídeos privados ou restritos.

## Execução local

Instale Python 3.12+, FFmpeg/FFprobe e Node.js 22+ (ou Deno compatível), e execute o aplicativo como descrito no README. A rota `/api/downloads/status` informa se as dependências foram encontradas. Os extras `yt-dlp[default]` incluem os componentes EJS usados pelo motor para compatibilidade atual com o YouTube.

Sem `DOWNLOAD_WORKER_URL`, o backend mantém uma fila no banco local. Um vídeo é processado por vez em um subprocesso separado. As tarefas aguardando na fila sobrevivem a reinícios; uma tarefa interrompida passa a falha e pode ser solicitada novamente. Execute apenas **um processo de backend por banco/volume**. A fila aceita todos os vídeos selecionados e processa um por vez; tarefas aguardando não expiram. A retenção de arquivos começa após a conclusão de cada download. O limite padrão por arquivo é 2 GiB e o tempo padrão por tarefa é uma hora, configuráveis. Garanta espaço em disco para downloads e arquivos temporários.

Os arquivos ficam em `downloads/exports/`, e expiram 24 horas após concluir. A fila remove arquivos expirados automaticamente. Um cookie HttpOnly identifica os downloads do navegador. Limpar os cookies impede recuperar seu histórico por esse navegador.

## Vercel + servidor de downloads

A Vercel atende a interface e as requisições JSON. A conversão roda em um serviço persistente com HTTPS. Os arquivos são entregues diretamente pelo worker, por links assinados válidos por dez minutos, para evitar enviar arquivos grandes pela função da Vercel. O botão Salvar renova o link antes de baixar.

1. Hospede `Dockerfile.worker` em um serviço que execute containers com volumes persistentes. O comando é `uvicorn app.download_worker:app --host 0.0.0.0 --port 8000 --workers 1`. O worker exige `DOWNLOAD_WORKER_TOKEN` e `DOWNLOAD_PUBLIC_URL`.
2. Gere uma chave: `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Armazene-a como variável secreta do worker e da Vercel.
3. No worker, configure `DOWNLOAD_PUBLIC_URL=https://seu-worker.example`, `DOWNLOAD_WORKER_TOKEN=<chave>` e `VERCEL` vazio. Use SQLite em volume persistente, ou PostgreSQL. Monte volumes em `/app/downloads` e `/app/database` quando usar SQLite.
4. Na Vercel, configure `DOWNLOAD_WORKER_URL=https://seu-worker.example` e a mesma `DOWNLOAD_WORKER_TOKEN`. Mantenha o PostgreSQL e as credenciais Google já usados pelas contas. Publique novamente a interface/API.
5. Confira `/api/downloads/status` pelo aplicativo. O worker não precisa das credenciais OAuth do Google para processar links públicos.

Para uma VPS com proxy HTTPS no próprio host, `compose.downloads.yml` fornece o worker e os volumes. Crie `.env` a partir de `.env.example`, preencha as variáveis do worker e execute `docker compose -f compose.downloads.yml up -d --build`. A porta do worker fica em `127.0.0.1:8002`; configure o proxy HTTPS para essa porta. Use timeout de streaming suficiente para servir os arquivos. Mantenha a proteção de acesso da aplicação pessoal na Vercel, conforme o README.

O worker só expõe sua API JSON com `Authorization: Bearer <chave>`. A interface nunca recebe essa chave. Os links de arquivo só dão acesso a um download e por tempo limitado. Listagens são limitadas ao identificador do navegador enviado pelo backend autenticado.

## Atualizações periódicas

O processo do backend/worker verifica e instala uma atualização ao iniciar e a cada 24 horas, enquanto estiver em execução. O padrão é o canal `nightly`, recomendado pelo yt-dlp para acompanhar mudanças do YouTube. `DOWNLOAD_UPDATE_CHANNEL=stable` seleciona lançamentos estáveis; `DOWNLOAD_UPDATE_HOURS` controla o intervalo; `DOWNLOAD_AUTO_UPDATE=false` desativa a instalação automática.

A atualização é instalada a partir do PyPI em um ambiente Python novo dentro de `downloads/engines/`. Antes de ativá-la, o adaptador testa as opções de MP3 e MP4. Cada tarefa captura o Python ativo quando começa, portanto uma atualização não troca seus arquivos durante o download. Se a instalação ou o teste falhar, a versão anterior continua ativa. Ambientes antigos são mantidos por sete dias; a versão base continua instalada no ambiente da aplicação.

O ambiente precisa conseguir acessar o PyPI, criar ambientes com `venv`/`ensurepip`, ter armazenamento gravável e espaço para eles. Node/FFmpeg vêm da instalação local ou da imagem Docker; atualizá-los exige atualizar essa instalação ou reconstruir a imagem. A atualização do motor melhora a compatibilidade, mas não garante acesso a vídeos restritos nem elimina bloqueios do YouTube.

Manutenção manual, executada da pasta `backend` (no worker Docker, execute com `python` em vez de `uv run python`):

```bash
uv run python manage_download_engine.py status
uv run python manage_download_engine.py update
uv run python manage_download_engine.py rollback
```

Reinicie o processo após manutenção manual para atualizar o estado exibido pelo servidor. Rollback exige uma atualização anterior com ambiente ainda disponível. Para manter a versão restaurada, desative as atualizações automáticas até investigar a regressão.

O workflow `.github/workflows/download-checks.yml` executa testes e build em pushes/PRs, manualmente e às segundas-feiras. Também testa o adaptador com a nightly atual. A atualização do worker ocorre independentemente desse workflow, sem precisar alterar o código ou fazer deploy diário. Os testes de conversão usam mídia sintética local e FFmpeg real; não publicam nem modificam vídeos do YouTube.

## Conteúdo privado e restrições

Conectar um canal permite listar seus vídeos pela API oficial. Para baixar conteúdo privado do próprio canal, pode ser necessário montar no worker um arquivo de cookies Netscape de uma sessão autorizada e definir `DOWNLOAD_COOKIES_FILE` com seu caminho. Proteja o arquivo e atualize-o quando a sessão expirar; nunca o versione nem envie pela interface. O servidor pode falhar mesmo para vídeos públicos por mudanças, bloqueios de rede, limites ou restrições do YouTube. A tela mostra o resultado de cada tarefa, permitindo uma nova tentativa depois que a causa for resolvida.

## Contrato da API

| Rota da aplicação | Uso |
| --- | --- |
| `GET /api/downloads/status` | Disponibilidade e estado do motor |
| `GET /api/downloads/channel/{channel_id}` | Vídeos do canal OAuth conectado |
| `POST /api/downloads/jobs` | Enfileira `{sources, format, resolution, channel_id?}`; retorna 202 |
| `GET /api/downloads/jobs` | Tarefas do navegador e links dos arquivos prontos |
| `GET /api/downloads/jobs/{id}/file` | Entrega local com verificação de propriedade |

O gateway de nuvem usa `/api/download-worker/status` e `/api/download-worker/jobs` com chave secreta. `/api/download-worker/files/{id}` exige uma assinatura válida e não aceita caminhos fornecidos pelo usuário.
# Site na Vercel com downloads locais

Abra `Iniciar Downloads.cmd` na raiz do projeto (Windows). O iniciador prepara as dependências, abre http://localhost:8011/downloads e mantém o serviço em execução. Requer Python, uv, Node.js/npm e FFmpeg/FFprobe instalados. Feche com Ctrl+C depois que os downloads terminarem.

No site publicado, selecione links ou vídeos do canal conectado, escolha MP3/MP4 e clique em **Enviar ao aplicativo local**. Abra o link gerado e confirme **Preparar** na página local. A seleção é validada no site e transferida sem credenciais OAuth. O download só começa após sua confirmação local.

Vercel e Neon continuam responsáveis pelo site e pelas contas conectadas. Arquivos e histórico de downloads ficam no computador, em SQLite. Não é necessário hospedar um servidor de downloads. Vídeos privados/restritos podem precisar de cookies autorizados configurados localmente; conectar o canal por OAuth não concede acesso ao extrator de mídia.

O motor verifica atualizações a cada 24 horas enquanto o aplicativo está aberto, com validação antes da ativação e opção de reversão. Um servidor remoto, descrito abaixo, é opcional.



## Preparar com um clique (Windows)

Abra `Iniciar Downloads.cmd` uma vez neste computador. Ele registra o protocolo `ytacervo` apenas para seu usuário, sem exigir administrador. Depois, no site, selecione vídeos e clique em **Preparar MP3**: autorize a abertura do aplicativo no navegador. O iniciador reutiliza o serviço existente ou inicia o serviço, abre a página local com a seleção e começa a fila automaticamente, sem repetir a seleção ou clicar novamente em Preparar. A execução pelo protocolo ocorre em segundo plano; erros de inicialização ficam em `downloads-launcher.log`. Python, uv, Node e FFmpeg continuam necessários.

Em **Levar tudo em um pacote**, o botão **Baixar todos os MP3s prontos** prepara e salva um ZIP em uma única ação, incluindo arquivos disponíveis mesmo se já tiverem sido salvos individualmente. Não refaz a conversão. Arquivos expirados precisam ser preparados novamente. A seleção personalizada de arquivos continua disponível.
