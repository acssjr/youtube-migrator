# Melhorias propostas para o Acervo

Este documento apresenta propostas. Apenas a seleção de downloads por playlist foi implementada nesta etapa. As demais ideias precisam de desenvolvimento; a ordem abaixo privilegia o trabalho recorrente com apresentações e repertório.

## Direção do produto

Organizar o acervo em quatro entidades: **obra**, **pessoa**, **execução** e **apresentação**. Uma obra pode ter várias execuções, compositores e arranjos; uma apresentação reúne execuções de diferentes obras. O vídeo é um registro de uma execução. A playlist é uma forma de publicar uma seleção, e não deve ser a única fonte de organização do acervo.

Exemplo: uma execução de Senhora Sant'Anna pode usar a biografia publicada do compositor, os dados da filarmônica e o rodapé atual do projeto Retreta. A curiosidade de Chimarrão continua vinculada a Chimarrão. O programa deve explicar a origem de cada bloco e preservar a redação aprovada.

## Primeira etapa: reduzir trabalho repetitivo

| Proposta | Como funcionaria | Ganho prático |
|---|---|---|
| Pacote de download da apresentação | Um pacote com arquivos numerados na ordem escolhida, lista de faixas e relatório dos itens que falharam. | Evitar clicar em Salvar para cada arquivo. |
| Repetir somente downloads com erro | Botão por tarefa e botão para repetir todas as falhas, preservando formato e qualidade. | Não reenviar um lote inteiro. |
| Pausar e cancelar a fila | Pausar novas tarefas, retomar a fila e cancelar itens aguardando; cancelamento da tarefa atual deve encerrar também a conversão. | Corrigir uma seleção e liberar o computador. |
| Destino e nomes dos arquivos | No aplicativo local, escolher pasta e padrão de nome: apresentação, posição, obra, compositor. Na versão web, oferecer pacote para salvar. | Arquivos organizados sem renomear manualmente. |
| Evitar downloads repetidos | Verificar histórico por vídeo, formato e qualidade; mostrar se o arquivo pronto ainda existe e permitir baixar novamente quando desejado. | Poupar banda e tempo sem bloquear uma repetição intencional. |
| Presets por filarmônica | Salvar nome oficial, redes sociais, texto institucional e preferências de título. | Evitar misturar referências de instituições. |
| Biblioteca de textos aprovados | Cadastrar os blocos exatos Sobre o compositor e Sobre o arranjador, com referência e versão. | Reutilizar o texto do usuário sem reescrita automática. |
| Rodapé universal versionado | Um modelo de links por projeto/filarmônica, com ordem e versão; atualizar apenas esse bloco nos vídeos escolhidos. | Acrescentar a próxima noite da Retreta sem mexer na biografia ou curiosidade da obra. |
| Atualizações com comparação e reversão | Mostrar antes/depois de título e descrição; guardar a versão anterior antes de aplicar. Restaurar também exige conferir alterações posteriores. | Corrigir um lote publicado sem perder conteúdo. |

## Segunda etapa: transformar os vídeos em um catálogo musical

| Proposta | Como funcionaria | Ganho prático |
|---|---|---|
| Ficha da obra | Nome principal, nomes alternativos, gênero, compositor, arranjador e observações aprovadas. | Encontrar a mesma música apesar de diferenças na grafia. |
| Nomes alternativos com revisão | Sugerir equivalências como Santana/Sant'Anna e abreviações de filarmônicas; confirmar antes de unificar. | Melhorar buscas sem fundir obras ou pessoas distintas. |
| Ficha da apresentação | Projeto, noite, data, local, filarmônicas e ordem do repertório; associação manual ou sugestão revisável. | Organizar uma noite completa em uma operação. |
| Busca combinada | Filtrar por obra, gênero, compositor, arranjador, filarmônica, apresentação, ano e ensaio/apresentação. | Buscar, por exemplo, marchas de um compositor executadas por uma banda em determinado projeto. |
| Playlists a partir de critérios | Criar uma seleção por compositor, gênero, banda ou apresentação; prévia dos itens e confirmação antes de atualizar o YouTube. | Produzir coleções temáticas consistentes. |
| Auditoria de playlists | Apontar itens repetidos, registros sem playlist, vídeos não consultáveis e possíveis divergências de apresentação/data. | Identificar lacunas sem remover vídeos automaticamente. |
| Comparar execuções da mesma obra | Reunir gravações por data e banda; permitir notas sobre interpretação e escolha de uma execução de referência. | Apoiar estudo do repertório e curadoria de melhores gravações. |
| Repertório tocado e novidades | Mostrar quais obras já foram executadas por cada banda e quando apareceram no catálogo. | Planejar programas e reconhecer obras novas no acervo cadastrado. |
| Exportar repertório | Gerar planilha e lista para programa de concerto com obra, gênero, autoria, ordem e links. | Reaproveitar a organização fora do YouTube. |

## Terceira etapa: preservação e estudo

| Proposta | Como funcionaria | Ganho prático |
|---|---|---|
| Backup dos metadados | Exportar títulos, descrições, IDs, links, ordem das playlists e fichas do catálogo em JSON e planilha; nunca incluir tokens OAuth. | Preservar a organização mesmo se um registro desaparecer. |
| Backup incremental dos arquivos | Relacionar cada vídeo ao arquivo original, calcular hash, registrar cópia e baixar somente o que falta quando solicitado. | Diferenciar original preservado de cópia obtida do YouTube. |
| Etiquetas do MP3 | Gravar título, compositor, arranjador, intérprete, projeto e capa a partir da ficha revisada. | Biblioteca de áudio utilizável em players e pesquisas. |
| Partituras vinculadas às obras | Associar documento/URL à obra e ao arranjo exato, com conferência de versão e permissões de acesso. | Abrir partitura e gravações de referência no mesmo lugar. |
| Marcações de estudo | Guardar início do trio, solo ou outra passagem como tempo e anotação; capítulos publicados somente após revisão. | Encontrar trechos sem procurar manualmente no vídeo inteiro. |
| Pendências do acervo | Tela com descrições vazias, autoria não confirmada, arquivos sem cópia, playlists incompletas e conexões com problema. | Saber o próximo trabalho útil sem percorrer centenas de vídeos. |
| Resumo de tarefas | Mostrar fila, concluídos, falhas e arquivos prontos; aviso de término quando o usuário ativar. | Deixar o lote trabalhando e acompanhar o resultado com clareza. |

## Fluxo desejado para uma nova noite da Retreta

1. Criar a apresentação com data, local, filarmônica e repertório.
2. Selecionar os arquivos e associar cada um à obra e ao arranjo correto.
3. Gerar títulos com os nomes oficiais e separadores já definidos.
4. Montar descrições com os blocos aprovados, mostrando a referência de cada trecho.
5. Conferir a prévia e enviar os vídeos em fila.
6. Associar os vídeos confirmados à playlist da apresentação.
7. Sugerir a inclusão do novo link no rodapé universal, com prévia dos vídeos afetados.
8. Exportar repertório, pacote de áudio e backup dos metadados.

## Ordem recomendada

**Primeiro:** pacote de downloads, repetir falhas e controles de fila. **Depois:** biblioteca de textos, rodapé versionado e comparação/reversão. **Em seguida:** fichas de obras/apresentações e busca combinada. Com os dados organizados, avançar para playlists por critérios, backups, etiquetas de áudio e integração com partituras.

### Limites que devem ficar claros na interface

- Consulta de metadados pela API e obtenção do arquivo de mídia são etapas diferentes. Ter acesso ao registro não garante que o motor consiga baixar um vídeo restrito.
- Quantidade sem limite fixo na fila não elimina limites de disco, tempo, tamanho por arquivo ou disponibilidade do vídeo.
- Sugestões de identidade, autoria, texto específico e associação à apresentação exigem evidência e revisão. Não criar fatos biográficos para preencher lacunas.
- Exportação e reversão podem proteger alterações realizadas pelo aplicativo a partir da implementação; não recuperam automaticamente versões antigas que nunca foram salvas.

Referências técnicas: [consulta dos itens de playlists](https://developers.google.com/youtube/v3/docs/playlistItems/list), [consulta dos vídeos](https://developers.google.com/youtube/v3/docs/videos/list) e [atualização de metadados](https://developers.google.com/youtube/v3/docs/videos/update).
