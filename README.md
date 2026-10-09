# Votos por bairro — São Paulo, eleições 2026

App Streamlit com quatro botões: Presidente, Deputado estadual, Deputado federal e Senador. Resultados na tela por cidade, bairro, escola/local e seção. Downloads CSV são opcionais.

## Instalação

Requer Python 3.11 ou superior. Na pasta extraída:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Como funciona agora

1. Clique no botão de um cargo. Antes desse clique, nenhum dado eleitoral é carregado.
2. O app obtém os arquivos necessários que ainda não existem e prepara somente os registros do cargo escolhido.
3. Digite o número do candidato: Presidente 2 dígitos; deputado estadual 5; deputado federal 4; senador 3.
4. Escolha cidade e bairro para detalhar escolas e seções. Outro candidato do mesmo cargo usa a base pronta.
5. Ao clicar em outro cargo, somente esse cargo é preparado. Ao retornar, o app reutiliza sua base e restaura o último número consultado na sessão.

Cada cargo tem seu próprio índice SQLite em data/indices. Arquivos brutos comuns são reaproveitados. Deputados e senador compartilham o ZIP estadual do TSE: o primeiro preparo de cada cargo ainda precisa percorrer esse arquivo, pois o ZIP não oferece acesso direto por cargo. Apenas os registros selecionados são gravados no índice. Presidente usa a fonte nacional, filtrando São Paulo. Bairros são um cadastro comum reaproveitado por turno. Isso reduz preparação desnecessária, mas não elimina o custo do primeiro download e da primeira leitura.

O botão lateral Atualizar / tentar novamente este cargo busca versões novas das fontes necessárias ao cargo ativo. Se uma fonte compartilhada mudar, os índices dos outros cargos serão reconstruídos quando esses cargos forem clicados. Sem atualização, trocar de candidato ou retornar a uma base preparada não relê o ZIP.

Presidente permite selecionar turno; os demais cargos usam o primeiro. Turnos ainda sem resultados não recebem estimativas. Se faltar uma fonte, o app avisa: sem locais, bairro Não identificado; sem totalização, totais não validados. Falha na fonte de votos impede a consulta daquele cargo.

## Fontes e importação manual

- Resultados, incluindo SP por seção, Presidente por seção e votação nominal por município/zona: https://dadosabertos.tse.jus.br/dataset/resultados-2026
- Cadastro de locais de votação: https://dadosabertos.tse.jus.br/dataset/eleitorado-2026

As URLs diretas estão em SOURCES no app e as páginas de referência aparecem na tela. Downloads registram URL, horário UTC, tamanho e SHA-256 em data/*.json. O hash identifica o arquivo, não certifica assinatura digital do TSE.

Para importar manualmente, preserve os CSVs oficiais, separador ponto e vírgula e codificação Latin-1. Coloque os recursos em data/secoes.zip (SP), data/secoes_presidente.zip (Presidente), data/totais.zip e data/locais.zip. Também são aceitos CSVs com esses mesmos nomes-base. ZIP tem prioridade sobre CSV. Remova metadados JSON antigos ao substituir uma base manualmente. A autenticidade de importações manuais não é certificada pelo app.

O leitor prefere o membro SP para cargos estaduais e BR/BRASIL para Presidente, sem somar arquivos nacionais e estaduais. ZIPs ambíguos são rejeitados. O recorte exige ano 2026, SG_UF=SP, cargo e turno selecionados e um único código de eleição na votação. A totalização usa o mesmo código de eleição.

## Definições e validações

Bairro é o bairro do local de votação, não a residência dos eleitores. O vínculo usa código TSE do município, zona e número do local, sem dedução por endereço ou nome. Ausências e conflitos ficam Não identificado. O nome da escola é preservado quando consta diretamente no resultado eleitoral. Grafias diferentes de bairro permanecem separadas.

Percentual nas cidades é a participação nos votos do candidato em SP; nos bairros, nos votos dele na cidade; nos detalhes, no recorte selecionado. Posição ordena territórios pelos votos desse candidato, com empates (1, 1, 3); não é classificação entre candidatos. Não inclui brancos, nulos ou votos de legenda. Denominador zero resulta em 0%.

Seções presentes na fonte sem registro para o número consultado recebem zero. Seções ausentes não são criadas. Número ausente em toda a base gera aviso e não comprova candidatura ou votação zero.

O app bloqueia duplicidades candidato/seção, contagens inválidas, mistura de eleições e locais conflitantes por seção. O cruzamento de bairros conserva linhas e votos. A soma dos bairros inclui os não identificados e deve coincidir com a cidade. A conferência independente compara cada município/zona com a votação nominal oficial e disponibiliza diferenças. Divergências são destacadas; não se declara conciliação. Datas e situações de votos distintas podem explicar diferenças. Não há afirmação de resultado definitivo ou completude apenas porque a soma fecha.

## Cache, atualização e espaço

Os índices são identificados por cargo, tipo de fonte, caminho, tamanho, data de modificação e versão do leitor. Não preserve artificialmente tamanho/horário ao substituir uma fonte. Índices novos só são publicados após concluir a preparação. As fontes são lidas em blocos de 100 mil linhas e apenas colunas necessárias são importadas.

O cache em memória tem limite de oito resultados e quatro cadastros de bairros; os índices de todos os cargos preparados permanecem em disco. Se um resultado sair do cache, sua consulta volta ao índice rápido, não ao ZIP. O armazenamento precisa de espaço adicional. Com o app parado, pode-se remover data/indices para liberar espaço ou forçar nova preparação. Se a hospedagem apagar o disco, será necessário preparar novamente.

## Testes

```bash
python -m unittest -v test_app.py
python benchmark.py
```

22 testes passaram: filtros dos cargos/turnos, São Paulo, botões, troca e retorno entre cargos, restauração do candidato, índice exclusivo do cargo clicado, reaproveitamento sem leitura do CSV, atualização de fonte, igualdade de resultados, duplicidades, mapeamentos ausentes/conflitantes, somas, percentuais e CSV.

Testes usam dados sintéticos temporários e nunca os apresentam como resultados eleitorais. A carga integral dos votos reais não foi realizada nesta entrega. A conciliação real é feita pelo app após obter as fontes. A medição anterior com 200 mil registros sintéticos encontrou 1,509 s de leitura completa contra 0,027 s para outra consulta com índice pronto; não representa o tempo de download, da base completa do TSE ou da hospedagem.
