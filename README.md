# Votos por bairro — São Paulo, 2026

Streamlit com botões de Presidente, Deputado estadual, Deputado federal e Senador. Esta versão restaura a leitura direta dos arquivos, sem preparar índices SQLite e sem exigir arquivos preparados no computador do usuário.

## Fluxo no Streamlit Cloud

1. Clique em um cargo. O servidor obtém os arquivos do TSE que ainda não possui.
2. Informe o número do candidato. O app lê os arquivos em blocos e filtra o cargo, turno, São Paulo e candidato.
3. Consulte cidades, bairros, escolas e seções na tela. Downloads CSV são opcionais.
4. Consultas recentes são guardadas em memória; voltar à mesma consulta reutiliza o resultado. Outro candidato ainda não consultado exige nova leitura. O cadastro de bairros tem cache separado.

Os arquivos ficam no servidor. Não há etapa de baixar ou preparar dados no seu computador. O botão Atualizar / tentar novamente este cargo busca versões novas no TSE. Atualizações de fonte invalidam o cache por caminho, tamanho e data de modificação. Se o servidor perder os arquivos ou reiniciar o cache, poderá ser necessário baixar ou ler novamente.

Deputados e senador compartilham o ZIP estadual; Presidente usa o ZIP nacional filtrado por SG_UF=SP. Os downloads e a leitura inicial ainda podem demorar. Esta versão evita o custo adicional de indexar todos os candidatos antes de mostrar a consulta. Não foi medido seu tempo real no Streamlit Cloud.

## Executar ou publicar

Para rodar Python 3.11 ou superior:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Para publicar, use app.py e requirements.txt no repositório ligado ao Streamlit Cloud. Não é necessário publicar bases prontas, SQLite ou arquivos brutos. As dependências são instaladas pelo serviço.

## Fontes

Resultados e recursos por seção/município/zona: https://dadosabertos.tse.jus.br/dataset/resultados-2026

Cadastro de locais: https://dadosabertos.tse.jus.br/dataset/eleitorado-2026

URLs exatas e páginas dos recursos estão em SOURCES e PAGES no app. Downloads registram origem, horário UTC, tamanho e SHA-256 na pasta data; esse hash identifica o arquivo recebido, não certifica assinatura digital. A data de geração da votação aparece na consulta. Não há dados fictícios na aplicação.

## Critérios e validações

- Ano 2026, São Paulo, cargo selecionado; primeiro turno para deputados/senador e turno selecionável para Presidente. Número: 2, 5, 4 ou 3 dígitos, respectivamente para Presidente, estadual, federal e senador.
- Bairro é o bairro do local de votação, não a residência do eleitor. Vínculo exato pelo código TSE do município, zona e local. Ausências/conflitos ficam Não identificado. Nomes de escola podem vir do resultado eleitoral. Não há inferência por endereço, geocodificação ou nome.
- Percentual das cidades: participação nos votos do candidato em SP; dos bairros: participação nos votos dele na cidade; dos detalhes: participação no recorte selecionado. Posição ordena territórios/locais pelos votos desse candidato e admite empates. Não é classificação entre candidatos nem percentual sobre todos os votos válidos.
- Ausência do candidato em toda a fonte gera aviso. Seção existente sem voto para esse número recebe zero; seções ausentes não são fabricadas.
- Duplicidade por candidato/seção, contagens inválidas e múltiplas eleições são bloqueadas. O cruzamento conserva votos e linhas. Soma dos bairros inclui Não identificado.
- Totais são comparados por município/zona com a votação nominal independente. Diferenças são exibidas e não recebem declaração de conciliação. Datas e situações dos votos podem divergir entre fontes. Sem arquivo de totais, os resultados ficam não validados; sem votação, a consulta fica indisponível.
- Cache em memória limitado a oito consultas e quatro cadastros de bairros. O último número de cada cargo é preservado na sessão, mas um resultado pode ser removido do cache quando seu limite é atingido.

## Testes

```bash
python -m unittest -v test_app.py
```

19 testes passaram, incluindo leitura direta, reaproveitamento de consulta sem reler CSV, obtenção de arquivos sem pré-processamento, navegação entre cargos, filtros, validações de votos, conflitos de bairro, totais e CSV. Usam dados sintéticos isolados. Não substituem a conciliação das bases reais do TSE nem medem desempenho na hospedagem.
