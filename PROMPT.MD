Atue como Cláudio, um Engenheiro DevOps e Arquiteto de Software Sênior.

Objetivo do Projeto:
Preciso que você crie a arquitetura e os arquivos de configuração para um sistema local chamado Auto Service. A ideia principal é ter quatro serviços distintos rodando em uma única máquina local, todos orquestrados por um único docker-compose.yml. Além disso, preciso de um serviço de "Hub" (um portal web central) rodando no mesmo ecossistema, onde eu possa acessar uma interface simples pelo navegador e, a partir de botões/links, ser redirecionado para a interface de cada um desses quatro serviços.

Os quatro repositórios/serviços que irão compor o Auto Service são:

Gerenciador de Arquivos: ownCloud/ocis (https://github.com/owncloud/ocis)

Removedor de Fundo: BackgroundRemover (https://github.com/nadermx/backgroundremover)

Ferramentas de PDF: Stirling-PDF (https://github.com/Stirling-Tools/Stirling-PDF)

OCR: PaddleOCR (https://github.com/PaddlePaddle/PaddleOCR)

Metodologia de Raciocínio (Tree of Thoughts - ToT):
Antes de gerar qualquer código, explore múltiplas linhas de pensamento para resolver este problema arquitetural. Siga os passos abaixo explicitamente na sua resposta:

Análise de Requisitos e Imagens: Analise como cada um desses repositórios é conteinerizado. Alguns possuem imagens Docker oficiais prontas para uso (como Stirling-PDF e oCIS), outros podem precisar de um Dockerfile customizado para expor uma API ou interface web (como BackgroundRemover e PaddleOCR, que geralmente são de linha de comando ou bibliotecas). Pense em como resolver a interface para os serviços que não possuem uma GUI nativa.

Mapeamento de Rede e Portas: Desenhe mentalmente a rede do Docker. Como o Hub (pode ser um Nginx simples com um index.html) vai rotear o tráfego para as portas corretas no localhost da máquina host? Quais portas externas devemos expor para evitar conflitos?

Avaliação de Caminhos (Branching & Pruning): - Caminho A: Fazer build de tudo do zero. (Rejeitado: demorado e complexo).

Caminho B: Usar imagens pré-construídas sempre que possível e criar wrappers web simples via Flask/FastAPI para as ferramentas de CLI (OCR e Background Remover), orquestrando tudo no Compose.

Escolha o caminho mais eficiente, robusto e que exija menos manutenção futura.

Resumo da Solução: Apresente a conclusão do seu pensamento e a estrutura final da arquitetura.