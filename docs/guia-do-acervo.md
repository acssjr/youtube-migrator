# Guia das ferramentas do Acervo

## Explorar

- **Pendências:** veja descrições vazias, créditos que precisam de revisão, datas de apresentações faltantes, rodapés desatualizados e a situação dos originais registrados. As informações são consultadas; nada é publicado pelo painel.
- **Buscar vídeos:** combine obra, compositor, arranjador, gênero, filarmônica, apresentação e intervalo de datas. Escolha se o período considera a publicação ou a apresentação. Datas desconhecidas permanecem desconhecidas.
- **Repertório:** reúna as execuções de cada filarmônica por obra, compositor e arranjador. A primeira referência documentada no canal não é necessariamente a estreia da obra.
- **Comparar execuções:** selecione gravações da mesma identidade musical, veja os créditos e datas lado a lado, abra os vídeos, guarde favoritos e anotações particulares.
- **Conferir playlists:** consulte itens repetidos, títulos duplicados, playlists vazias, vídeos privados ou indisponíveis, vídeos fora de playlists e itens esperados das apresentações cadastradas. A auditoria não remove itens.

## Organizar

- **Obras:** cadastre a obra, o gênero, o compositor, o arranjador, grafias alternativas e notas. Sugestões extraídas dos títulos do canal só entram no catálogo depois de conferidas. Grafias alternativas são consideradas juntamente com compositor e arranjador.
- **Apresentações:** registre projeto, noite, data da apresentação, local, filarmônica, playlist e vídeos. A data da apresentação não é preenchida usando a publicação.
- **Filarmônicas:** guarde nome oficial, redes sociais, texto institucional, visibilidade e preferências de título. Na página de uploads, aplique as preferências ao lote antes de enviar.
- **Criar playlists:** escolha critérios, gere a prévia, confira os vídeos e a ordem, selecione uma playlist própria ou dê nome à nova e publique explicitamente. Uma falha pode ser retomada sem adicionar novamente os vídeos já incluídos.

## Textos e descrições

- **Textos aprovados:** cole o texto completo ou consulte os blocos publicados em um vídeo do canal conectado. Informe o nome exato e aprove o bloco. Biografias de compositor e arranjador são usadas exclusivamente para a pessoa e o papel correspondentes, sem reescrita. A versão aprovada mais recente vence.
- **Rodapés:** cadastre os links e o texto atual por projeto/filarmônica. Selecione os vídeos, compare antes/depois e publique. A ferramenta troca apenas blocos reconhecidos de playlists; quando não reconhece um bloco seguro, acrescenta o modelo para preservar o restante.
- **Histórico de alterações:** compare título e descrição antes de publicar. Uma cópia do conteúdo anterior é guardada antes da chamada ao YouTube. A restauração confere se o vídeo mudou depois da revisão para evitar apagar uma alteração posterior.

Os textos aprovados também são consultados nas sugestões de descrições dos vídeos publicados e nos rascunhos de upload. Os nomes cadastrados são oferecidos nos seletores de compositores, arranjadores e filarmônicas.

## Preservar

- **Backup dos metadados:** baixe JSON com descrições exatas, status, playlists ordenadas, catálogo, versões e revisões, ou CSV dos vídeos. Tokens e credenciais não são exportados. A importação tem prévia e confirmação, acrescenta registros e histórico, ignora duplicatas exatas e preserva os dados existentes. Os dados do YouTube no backup são referência e não são publicados pela importação.
- **Arquivos originais:** selecione arquivos ou uma pasta, associe os IDs dos vídeos e salve um inventário. SHA-256 é calculado em blocos pequenos. O inventário fica na nuvem; os vídeos não são enviados ao banco.
- **Backup incremental:** no Chrome/Edge, selecione uma pasta de destino e confira/copie os arquivos. Conteúdos idênticos são mantidos. Arquivos diferentes com o mesmo caminho só são substituídos quando essa opção for marcada. Cancelar interrompe o arquivo em andamento sem alterar a origem. A estrutura das pastas é preservada.

## Downloads

- Selecione links, vídeos do canal ou uma playlist, sem limite de quantidade por lote.
- A fila prepara um arquivo de cada vez. Pause os próximos, retome, reorganize os aguardando ou cancele um item, inclusive a conversão em andamento.
- Repita somente as falhas; formato e resolução são preservados. Trabalhos já na fila e arquivos prontos válidos são reaproveitados.
- Escolha pasta e padrão dos nomes no Chrome/Edge, ou use os downloads normais do navegador. A autorização da pasta precisa ser refeita quando a página é reaberta.
- Prepare um ZIP com os arquivos numerados na ordem selecionada, uma lista de faixas e um relatório das falhas. Arquivos disponíveis não são baixados novamente.
- Edite as etiquetas dos MP3 prontos: título, intérprete/filarmônica, compositor, álbum/projeto, gênero, ano, faixa e notas. Somente os campos marcados mudam; um campo marcado vazio remove seu valor. Os dados podem ser sugeridos pelo título para revisão. Isso não altera o YouTube.

Os arquivos preparados têm retenção temporária. Salve os arquivos ou o pacote antes de expirarem. Downloads, pacotes, controles e etiquetas funcionam no aplicativo de downloads ou no worker persistente configurado; o site em nuvem envia a seleção ao aplicativo quando não há worker.

## Escopo desta etapa

Implementadas as melhorias 1–15, 17–19 e 22. Exportação de repertório/programas (16), partituras (20) e marcações de estudo (21) ficaram fora do escopo solicitado.
