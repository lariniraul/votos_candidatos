# Votos por bairro — SP 2026

App Streamlit para Presidente, deputado estadual, deputado federal e senador em 2026, com resultados restritos a São Paulo. Menu de cargo e consulta por número com tamanho adequado, lista de cidades, seleção de cidade, bairros, escolas/locais, seções e exportações CSV UTF-8 com BOM (separador `;`). Não inclui votos de exemplo na aplicação.

## Executar

Requer Python 3.11 ou superior e acesso à internet para baixar os dados.

```bash
python -m venv .venv
```

No Windows (PowerShell):

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

No Linux/macOS:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Abra o endereço local mostrado pelo Streamlit. Clique em **Baixar / atualizar arquivos do TSE**, aguarde os três arquivos do cargo selecionado e informe o número. Escolha a cidade e depois um bairro para ver escolas e seções. A aplicação mantém os arquivos na pasta `data` ao lado de `app.py`; downloads podem ser grandes e demorar. Reserve alguns GB de disco e memória. A primeira consulta prepara índices SQLite em disco, em blocos de 100 mil linhas. As consultas seguintes usam esses índices, inclusive para outros candidatos e cargos presentes na mesma fonte, sem percorrer o CSV/ZIP novamente.

## Fontes oficiais verificáveis

Recursos localizados no portal do TSE em 09/10/2026:

- [SP — votação por seção](https://dadosabertos.tse.jus.br/dataset/resultados-2026/resource/30378d01-7c4a-43a8-84c8-4fc7499a9efe): `NR_VOTAVEL`, `QT_VOTOS`, município, zona, seção e local.
- [Votação nominal por município e zona](https://dadosabertos.tse.jus.br/dataset/resultados-2026/resource/c807b826-21ff-4bcf-97ca-d86482656320): conferência independente usando `NR_CANDIDATO` e `QT_VOTOS_NOMINAIS`.
- [Eleitorado por local de votação](https://dadosabertos.tse.jus.br/dataset/eleitorado-2026/resource/300626b4-2b24-4d2e-b4fc-46b569cfffe5): identificação do bairro e escola pelo cadastro de locais do ano.

Links diretos estão em `SOURCES`, no app. Cada download registra URL, página de origem, horário UTC, tamanho e SHA-256 em `data/*.json`, visíveis em “Fontes e rastreabilidade”. O hash identifica o arquivo recebido; não é assinatura digital do TSE. A data de geração declarada no arquivo de votos também aparece na tela. As bases podem ter datas diferentes, retificações e situações de votos que produzam divergências; conciliação não certifica resultado definitivo ou situação jurídica da candidatura.

## Importação manual e indisponibilidade

Se o TSE estiver fora do ar, baixe os recursos pelas páginas acima e copie os arquivos para `data/secoes.zip`, `data/locais.zip` e `data/totais.zip`. Alternativamente use `.csv` com os mesmos nomes-base. ZIP tem prioridade sobre CSV: mantenha apenas a versão desejada de cada base. CSVs devem conservar o formato oficial, `;` e codificação Latin-1. Em ZIP, o leitor prefere membro terminado em `_SP.csv`, depois `_BRASIL.csv`, ou um único CSV; um conjunto ambíguo é rejeitado para evitar dupla contagem.

Importações manuais não têm autenticidade certificada pelo app. Remova eventuais arquivos JSON antigos ao substituir manualmente a base. Não use planilha truncada, anos anteriores ou dados de outro cargo. Nenhum dado de 2022 é apresentado como se fosse de 2026. Se o leiaute mudar, o app avisa sobre as colunas ausentes; é necessário adaptar o leitor ao novo dicionário oficial.

Sem votação disponível, a tela informa indisponibilidade. Sem locais, votos continuam visíveis e o bairro fica **Não identificado**; a escola é preservada quando informada no próprio arquivo de votação. Sem arquivo independente de totais, a tela marca os resultados como **não validados**. Falha de atualização preserva a base anterior e informa o erro; confira o horário de download. Não há fallback para dados fictícios.

## Definições e limites

- Recorte obrigatório: `ANO_ELEICAO=2026`, `SG_UF=SP`, `CD_CARGO=6`, `NR_TURNO=1`. O arquivo de votos deve ter apenas um `CD_ELEICAO` nesse recorte; a totalização usa o mesmo código. Não se presume que um número pertença à mesma pessoa de outra eleição.
- Votos: registros do número consultado. Ausência do número em toda a base gera aviso, não uma afirmação de votação zero. Seções presentes na base sem registro desse número recebem zero; seções inteiramente ausentes não são fabricadas. Cidades listadas são as presentes no arquivo.
- Percentual nas cidades: votos do candidato na cidade / votos do candidato em SP. Nos bairros: votos do candidato no bairro / votos do candidato na cidade. Nos detalhes: participação nos votos do candidato no recorte selecionado. Denominador zero resulta em 0%. **Não é percentual sobre votos válidos de todos os candidatos.**
- Posição: ranking dos territórios/locais por votos do candidato consultado, não classificação do candidato contra adversários. Empates compartilham posição, com salto na próxima (1, 1, 3).
- Bairro significa **bairro do local de votação**, não residência dos eleitores. Votos são agregados; o app não identifica como uma pessoa votou.
- Vínculo exato por código TSE do município + zona + número do local, no cadastro de 2026. Código TSE não é código IBGE. A seção vem do arquivo de votação. Não há aproximação por nome, CEP, endereço, geocodificação ou lista presumida de bairros.
- Nomes de bairros são preservados; grafias diferentes permanecem separadas. Campos vazios, `#NULO#`, `#NE#`, `-1` e `-3` viram Não identificado. Locais com atribuições conflitantes de bairro/escola também viram Não identificado. Repetições cadastrais idênticas são removidas antes do cruzamento.
- Um mesmo número de local em zonas diferentes é tratado separadamente. Locais podem não ser escolas; o rótulo “Escolas / locais” inclui ambos.

## Validação

O app bloqueia contagens inválidas/negativas, duplicação de candidato por seção, mistura de eleições e seção com locais conflitantes. O cruzamento é muitos-para-um e deve conservar quantidade de linhas e soma dos votos. A soma dos bairros deve coincidir com o total municipal, incluindo Não identificado. A conferência independente compara **cada município/zona**, não apenas o total estadual, e oferece CSV com diferenças. Divergências ficam destacadas e os resultados são exibidos para investigação, sem declaração de conciliação. Isso não prova que uma base esteja completa: só a comparação oficial e as condições de publicação permitem avaliar cobertura.

## Testar

```bash
python -m unittest -v test_app.py
```

Os testes usam dados sintéticos isolados em arquivos temporários: filtros, zeros, duplicidades entre blocos, eleições misturadas, contagens inválidas, colunas ausentes, bairros conflitantes/ausentes, preservação de totais, percentuais e empates, divergências que se compensam no total, CSV e fluxo da interface com `streamlit.testing.v1.AppTest`. Nenhuma fixture é instalada como resultado eleitoral. A execução desses testes não valida os votos reais de 2026; é necessário baixar as bases oficiais e observar a conciliação na aplicação.

## Verificação desta entrega

Em 09/10/2026: 20 testes passaram (incluindo interface vazia e navegação com dados sintéticos). Ambiente: Python 3.13.2, pandas 2.3.3, Streamlit 1.65.0 e requests 2.34.2. Os três links diretos responderam HTTP 200; cabeçalhos foram inspecionados em pequenas amostras dos ZIPs oficiais. Não foi realizada nesta entrega a carga integral e conciliação dos votos reais. A aplicação faz essa conferência após baixar os arquivos.

## Menu de cargos

Escolha o cargo na barra lateral antes de informar o número. Presidente usa 2 dígitos, deputado estadual 5, deputado federal 4 e senador 3. O número de cada cargo é mantido separadamente; os filtros e o cache incluem cargo e turno para não misturar consultas. Os resultados continuam nas tabelas da tela; CSV é opcional.

Presidente usa o recurso nacional de seções do TSE, filtrando SG_UF=SP, e o membro BR/BRASIL da totalização. Para importação manual, salve a votação presidencial em data/secoes_presidente.zip (ou .csv). O cadastro de locais é filtrado pelo turno selecionado. Não há substituição por cadastro de outro turno: se não houver vínculo, o bairro fica Não identificado. Deputados e senador continuam usando data/secoes.zip. O botão de atualização busca somente a base de seções do cargo selecionado, locais e totais. Turnos sem resultados disponíveis não exibem estimativas.

Fonte presidencial: https://dadosabertos.tse.jus.br/dataset/resultados-2026 (recurso Presidente — Votação por seção eleitoral — 2026). URL: https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_BR.zip . A seleção de BR tem prioridade sobre SP apenas na leitura presidencial.

Os 20 testes incluem filtros dos quatro cargos, exclusão de outras UFs/turnos, segundo turno presidencial, seleção do membro BR para totais e troca de cargos na interface. A extensão presidencial foi testada com dados sintéticos; a carga integral dos dados reais continua não realizada nesta entrega.

## Desempenho e base rápida

Votos e totalização são preparados em data/indices, usando SQLite da biblioteca padrão do Python (sem dependência adicional). Só colunas necessárias e registros de SP/2026 dos quatro cargos são guardados. Os índices são identificados por caminho, tamanho e data de modificação da fonte, tipo de base e versão do leitor. Uma atualização normal invalida automaticamente o índice. Não preserve artificialmente tamanho e horário ao substituir uma fonte. A preparação publica o índice somente após concluir e conferir que a fonte não mudou. Bases antigas ficam no disco: com o app parado, a pasta data/indices pode ser removida para liberar espaço ou forçar reconstrução.

O cadastro de bairros tem cache independente por arquivo e turno. O cache de resultados é limitado a oito consultas e o de bairros a quatro entradas, evitando crescimento ilimitado em memória. Os índices continuam em disco após reiniciar o processo se o ambiente preservar a pasta; se o armazenamento for apagado, haverá nova preparação. A primeira consulta e o download ainda podem ser demorados, e preparar índices pode ser mais lento que uma única leitura antiga. É uma troca de custo inicial por consultas subsequentes rápidas, com necessidade de espaço adicional em disco.

Medição local sintética (200 mil registros): leitura anterior 1,509 s; preparação + primeira consulta 2,643 s; outro candidato com índice pronto 0,027 s (56,5 vezes mais rápido nessa consulta). Resultados idênticos. Esse teste mede a leitura de votos, não download, renderização, carga completa do TSE ou desempenho da hospedagem. Reproduza com python benchmark.py.

Os 20 testes também verificam igualdade entre leitores, reutilização sem reler o CSV, invalidação após atualização e preservação da detecção de duplicidades.
