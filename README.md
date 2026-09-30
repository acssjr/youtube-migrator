# YouTube Channel Video Migrator

## Uploads em lote

Em **Uploads**, selecione até 50 vídeos do computador e prepare as informações antes de iniciar a fila. O nome do arquivo serve apenas como identificação. O título é montado com gênero opcional, nome da obra, compositor, arranjador opcional e filarmônica, separados por ` — `, sem campos vazios. Compositores, arranjadores e filarmônicas são sugeridos a partir dos títulos existentes no canal; os campos também aceitam novos nomes. A visibilidade e a filarmônica podem ser aplicadas ao lote, e cada vídeo pode ser ajustado individualmente.

**Buscar descrições no acervo** reutiliza as regras da ferramenta Descrições, apresenta a referência e permite editar o texto antes do upload. Os arquivos são enviados diretamente do navegador à API do YouTube em blocos de 8 MiB. A Vercel recebe apenas as consultas de metadados e de autorização. O token de acesso temporário permanece em memória; o token de atualização e o segredo OAuth permanecem no backend.

A fila mantém rascunhos, progresso e URLs de sessão no armazenamento deste navegador. Mantenha a aba aberta durante o envio. Pausas e falhas são retomadas consultando primeiro o progresso confirmado pelo YouTube. Ao recarregar ou reabrir o site, selecione novamente os mesmos arquivos (nome, tamanho e data de modificação), pois o navegador não pode recuperar automaticamente o acesso ao disco. A fila continua se você trocar de ferramenta dentro do site. Falhas interrompem a fila para permitir a correção, e sessões expiradas nunca são reiniciadas automaticamente. As URLs de sessão são temporárias e devem ser tratadas como dados privados.

O YouTube pode restringir a privados os uploads de projetos sem auditoria. A interface mostra a visibilidade retornada pela API e não promete que a solicitação de público/não listado será atendida. “Enviado” significa que o upload foi aceito; o processamento do vídeo continua no YouTube.

Validação: `npm run test:uploads`, `npm run build` em `frontend/`, e `uv run python -m unittest discover -s tests -q` em `backend/`.

## Downloads de áudio e vídeo

A ferramenta **Downloads** prepara MP3 e MP4 por link e pelos vídeos do canal conectado. Inclui fila, histórico, seleção de qualidade e atualização automática do motor a cada 24 horas, com preservação da versão anterior em caso de falha na instalação. A versão na Vercel conecta a um servidor persistente de downloads; a execução local usa o próprio backend.

Veja [configuração, atualização e API de downloads](docs/downloads.md), incluindo `Dockerfile.worker`, volumes persistentes e variáveis de ambiente para a Vercel.

## Descrições em lote

A interface agora abre na ferramenta **Descrições**. Conecte o canal em **Configurações**, escolha até 50 vídeos sem descrição e clique em **Buscar descrições**. O aplicativo percorre todo o histórico de uploads do canal pela YouTube Data API, apresenta uma sugestão por vídeo e mostra as fontes usadas. Você pode corrigir a obra, o compositor e o arranjador antes da busca, além de editar cada texto antes de publicar o lote.

### Versão web na Vercel

O projeto `youtube-acervo-aio` usa Vercel Services: Vite em `frontend/` e FastAPI em `backend/`. A versão web oferece **Descrições**, **Uploads**, conexão de canal e **Downloads** quando um worker estiver configurado. A migração segue somente no aplicativo local porque sua fila atual depende de um processo e armazenamento permanentes.

Para ativar a conexão Google na Vercel, configure `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` como variáveis secretas de produção, além de um `DATABASE_URL` PostgreSQL persistente. Configure `GOOGLE_REDIRECT_URI=https://youtube-acervo-aio.vercel.app/api/auth/callback` e adicione esse mesmo URI ao cliente OAuth no Google Cloud. Faça um novo deploy após alterar as variáveis. Os tokens OAuth ficam criptografados no PostgreSQL; um cookie `HttpOnly`, `Secure` e `SameSite=Lax`, válido por um ano, identifica as contas do navegador. Mantenha a proteção de acesso da Vercel ativa para este uso pessoal.

O preenchimento segue esta ordem:

1. Outra publicação da mesma obra: usa o texto específico da obra.
2. Outra obra do mesmo compositor: usa apenas um parágrafo identificável sobre ele.
3. Outro arranjo do mesmo arranjador: usa apenas o crédito do arranjador.

Os blocos com links vêm da publicação **mais recente que contenha links**. A API informa a data de publicação do vídeo; ela não informa quando a descrição foi editada. Se não houver referência segura, o aplicativo deixa o campo vazio para revisão. Antes de gravar, confirma novamente que o vídeo pertence ao canal e continua sem descrição. Os resultados do lote indicam o que foi publicado, ignorado ou falhou.

Esta função usa os escopos OAuth já declarados pelo projeto, inclusive `youtube.force-ssl`, necessário para atualizar metadados. Canais conectados anteriormente sem esse escopo precisam ser reconectados. A migração continua disponível como utilidade separada.

Uma ferramenta local automatizada em React, TypeScript e Python (FastAPI) para migração de vídeos entre canais do YouTube gerenciados por você.

> [!IMPORTANT]
> **Esta ferramenta foi projetada exclusivamente para uso pessoal ou organizacional.** Ela serve para transferir vídeos entre canais nos quais você é o proprietário ou administrador. Não utilize esta ferramenta para copiar conteúdo de terceiros.

---

## 📂 Estrutura do Projeto

O projeto é estruturado de forma desacoplada em Frontend e Backend, mantendo arquivos limpos e separação de responsabilidades.

```
youtube-migrator/
│
├── backend/                  # Servidor API FastAPI
│   ├── app/
│   │   ├── api/              # Rotas HTTP (Auth, Canais, Migrações, etc.)
│   │   ├── config/           # Configurações globais e diretórios
│   │   ├── database/         # Sessão do SQLite e inicialização
│   │   ├── models/           # Modelos de dados do SQLModel (Tokens, Tarefas)
│   │   ├── repositories/     # Camada de persistência / Acesso a banco
│   │   ├── schemas/          # Validação e serialização de dados (Pydantic)
│   │   └── services/         # Regras de negócio (OAuth, Youtube, yt-dlp, Fila)
│   └── pyproject.toml        # Dependências gerenciadas pelo uv
│
├── frontend/                 # Interface React + Vite
│   ├── src/
│   │   ├── components/       # Componentes visuais e UI (shadcn base)
│   │   ├── layouts/          # Layout principal (DashboardLayout)
│   │   ├── pages/            # Telas (Migração, Configuração, Logs)
│   │   ├── services/         # Comunicação com a API (fetch wrapper)
│   │   ├── types/            # Tipos e interfaces TypeScript
│   │   └── lib/              # Utilitários (classes condicionais cn)
│   ├── package.json          # Dependências npm
│   └── vite.config.ts        # Configuração do Vite (Proxy da API integrado)
│
├── database/                 # Banco de dados SQLite local
├── downloads/                # Pasta temporária para downloads de vídeos
├── tokens/                   # Pasta para arquivos de credenciais
├── logs/                     # Arquivos de logs persistentes
│
├── .env.example              # Modelo de variáveis de ambiente
├── run.py                    # Script de inicialização automática simplificado
└── README.md                 # Instruções de configuração
```

---

## 🚀 Como Executar

### Deploy na Vercel

O site e a API FastAPI são publicados pelo `vercel.json`. Para conectar contas no deploy,
configure `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` e um
`DATABASE_URL` PostgreSQL persistente no ambiente de produção. No cliente OAuth do
Google, autorize exatamente `https://youtube-acervo-aio.vercel.app/api/auth/callback`.

As contas ficam no PostgreSQL com os tokens OAuth criptografados. O navegador mantém
somente um identificador aleatório em cookie seguro, válido por um ano. Assim, os
vínculos sobrevivem a novos deploys e várias contas podem ser conectadas ao mesmo
navegador. Limpar os cookies ou usar outro navegador exige conectar as contas de novo;
o Google também pode revogar ou expirar um token de atualização.

O deploy da Vercel atende às ferramentas de descrição. A migração de arquivos grandes
precisa de um worker e armazenamento persistentes em outro serviço de nuvem.

### 🛠️ Pré-requisitos

1. **Python 3.12+** instalado.
2. **Node.js 18+** instalado.
3. Gerenciador de pacotes Python **`uv`** (recomendado):
   ```bash
   pip install uv
   ```

### 🗝️ Configurando as Credenciais do Google (YouTube API)

Como este aplicativo funciona localmente em sua máquina, você precisa registrar sua própria aplicação na plataforma Google Cloud Console:

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Crie um novo projeto.
3. No painel, vá em **APIs e Serviços** > **Biblioteca** e ative a **YouTube Data API v3**.
4. Configure a **Tela de consentimento OAuth** (OAuth Consent Screen):
   - Escolha o tipo **Externo**.
   - Insira as informações de suporte (nome do app, e-mail).
   - Adicione os escopos necessários: `../auth/youtube.readonly` e `../auth/youtube.upload` ou `../auth/youtube.force-ssl`.
   - Adicione seus e-mails de teste (a conta do YouTube de origem/destino precisa estar na lista de usuários de teste enquanto o app estiver em modo "Publicação de Teste").
5. Vá em **Credenciais** > **Criar Credenciais** > **ID do cliente OAuth**:
   - Tipo de aplicativo: **Web Application** (Aplicação Web).
   - Adicione o seguinte URI de redirecionamento autorizado: `http://localhost:8000/api/auth/callback`.
6. Após criar, clique em **Fazer download do JSON** da credencial.
7. Renomeie o arquivo baixado para `client_secret.json` e coloque-o na **raiz** do projeto `youtube-migrator/`.

### 🏁 Iniciando o Projeto

Na raiz do projeto, execute o inicializador automático:

```bash
python run.py
```

O script realizará automaticamente as seguintes ações:
- Criará o ambiente virtual e instalará as dependências do Python.
- Instalará as dependências do frontend (React).
- Iniciará o backend FastAPI em `http://127.0.0.1:8000`.
- Iniciará o frontend React/Vite em `http://localhost:5173`.
- Abrirá automaticamente o navegador apontando para a interface.

---

## ⚙️ Configurações e Logs

- Os arquivos de tokens e bancos de dados SQLite são armazenados localmente e nunca compartilhados fora do seu ambiente de execução.
- Logs em tempo real de downloads e uploads estão localizados no diretório `/logs`:
  - `downloads.log`: Progresso do yt-dlp e informações de download.
  - `uploads.log`: Detalhes de envio e respostas da YouTube API v3.
  - `errors.log`: Apenas falhas críticas.


## Organização e preservação do acervo

As ferramentas de catálogo, textos aprovados, rodapés, revisões, playlists, repertório, backups e originais estão na área **Acervo**. Consulte [o guia das ferramentas](docs/guia-do-acervo.md). Os dados do catálogo usam o banco configurado e são isolados por proprietário na versão em nuvem. A edição do YouTube sempre exige uma ação explícita de publicação.
