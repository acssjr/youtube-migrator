# YouTube Channel Video Migrator

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
