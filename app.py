"""Eleições 2026 / SP / deputado federal. Execute: streamlit run app.py."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import zipfile

import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
UNKNOWN = "Não identificado"
BASE = "https://cdn.tse.jus.br/estatistica/sead/odsele/"
SOURCES = {
    "secoes": BASE + "votacao_secao/votacao_secao_2026_SP.zip",
    "locais": BASE + "eleitorado_locais_votacao/eleitorado_local_votacao_2026.zip",
    "totais": BASE + "votacao_candidato_munzona/votacao_candidato_munzona_2026.zip",
}
PAGES = {
    "secoes": "https://dadosabertos.tse.jus.br/dataset/resultados-2026/resource/30378d01-7c4a-43a8-84c8-4fc7499a9efe",
    "locais": "https://dadosabertos.tse.jus.br/dataset/eleitorado-2026/resource/300626b4-2b24-4d2e-b4fc-46b569cfffe5",
    "totais": "https://dadosabertos.tse.jus.br/dataset/resultados-2026/resource/c807b826-21ff-4bcf-97ca-d86482656320",
}
ZONE = ["CD_MUNICIPIO", "NR_ZONA"]
SECTION = ZONE + ["NR_SECAO"]
LOCAL = ZONE + ["NR_LOCAL_VOTACAO"]


def download(kind):
    """Download atômico; falhas nunca substituem o arquivo anterior."""
    DATA.mkdir(exist_ok=True)
    path = DATA / f"{kind}.zip"
    temp = DATA / f"{kind}.part"
    digest = hashlib.sha256()
    try:
        with requests.get(SOURCES[kind], stream=True, timeout=(15, 90)) as r:
            r.raise_for_status()
            with temp.open("wb") as out:
                for block in r.iter_content(1024 * 1024):
                    out.write(block)
                    digest.update(block)
        with zipfile.ZipFile(temp) as archive:
            if not any(n.lower().endswith(".csv") for n in archive.namelist()):
                raise ValueError("O recurso não contém CSV.")
        temp.replace(path)
        meta = {"url": SOURCES[kind], "pagina": PAGES[kind],
                "baixado_em_utc": datetime.now(timezone.utc).isoformat(),
                "sha256": digest.hexdigest(), "bytes": path.stat().st_size}
        path.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    finally:
        temp.unlink(missing_ok=True)
    return path


def chunks(path):
    """Lê sem extrair ZIP; prefere membro SP para não duplicar BR e UFs."""
    def reader(handle):
        return pd.read_csv(handle, sep=";", encoding="latin-1", dtype=str,
                           keep_default_na=False, chunksize=100_000)
    if path.suffix.lower() == ".csv":
        yield from reader(path)
        return
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        sp = [n for n in names if Path(n).stem.upper().endswith("_SP")]
        br = [n for n in names if Path(n).stem.upper().endswith("_BRASIL")]
        selected = sp or br or names
        if len(selected) != 1:
            raise ValueError("ZIP ambíguo: use o CSV de SP ou um único CSV nacional.")
        with archive.open(selected[0]) as handle:
            yield from reader(handle)


def require(frame, columns):
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError("Colunas ausentes: " + ", ".join(sorted(missing)))


def normalize(frame):
    frame = frame.copy()
    frame.columns = [c.strip().lstrip("\ufeff").removeprefix("ï»¿") for c in frame.columns]
    for col in frame:
        frame[col] = frame[col].str.strip()
    for col in set(SECTION + ["NR_LOCAL_VOTACAO", "NR_VOTAVEL", "NR_CANDIDATO", "CD_CARGO", "NR_TURNO", "ANO_ELEICAO"]) & set(frame):
        frame[col] = frame[col].str.replace(r"^0+(?=\d)", "", regex=True)
    return frame


def scope(frame, election=True):
    require(frame, ["SG_UF", "ANO_ELEICAO"] if election else ["SG_UF", "AA_ELEICAO"])
    year = "ANO_ELEICAO" if election else "AA_ELEICAO"
    keep = (frame.SG_UF == "SP") & (frame[year] == "2026")
    if election:
        require(frame, ["CD_CARGO", "NR_TURNO", "CD_ELEICAO"])
        keep &= (frame.CD_CARGO == "6") & (frame.NR_TURNO == "1")
    return frame.loc[keep].copy()


def vote_int(values):
    if not values.str.fullmatch(r"\d+").all():
        raise ValueError("Contagem de votos inválida ou negativa.")
    return values.astype("int64")


def read_votes(path, number):
    rows, universe, elections, dates = [], [], set(), set()
    for raw in chunks(path):
        f = scope(normalize(raw))
        require(f, SECTION + ["NM_MUNICIPIO", "NR_VOTAVEL", "QT_VOTOS"])
        elections.update(f.CD_ELEICAO.unique())
        if "DT_GERACAO" in f:
            dates.update(f.DT_GERACAO.unique())
        if "NR_LOCAL_VOTACAO" not in f:
            f["NR_LOCAL_VOTACAO"] = ""
        f["Escola_secoes"] = clean_label(f.NM_LOCAL_VOTACAO) if "NM_LOCAL_VOTACAO" in f else UNKNOWN
        universe.append(f[SECTION + ["NM_MUNICIPIO", "NR_LOCAL_VOTACAO", "Escola_secoes"]].drop_duplicates())
        hit = f[f.NR_VOTAVEL == number].copy()
        hit["Votos"] = vote_int(hit.QT_VOTOS)
        rows.append(hit[SECTION + ["Votos"]])
    if len(elections) != 1:
        raise ValueError("Arquivo vazio para o recorte ou contém mais de uma eleição.")
    votes = pd.concat(rows, ignore_index=True)
    if votes.duplicated(SECTION).any():
        raise ValueError("Votos duplicados para candidato/seção; não serão somados.")
    places = pd.concat(universe, ignore_index=True).drop_duplicates()
    if places.duplicated(SECTION).any():
        raise ValueError("Seção associada a locais ou municípios conflitantes.")
    result = places.merge(votes, on=SECTION, how="left", validate="one_to_one")
    result["Votos"] = result.Votos.fillna(0).astype("int64")
    return result, next(iter(elections)), sorted(dates), not votes.empty


def clean_label(series):
    return series.str.strip().replace({"": UNKNOWN, "#NULO#": UNKNOWN,
        "#NE#": UNKNOWN, "#NULO": UNKNOWN, "#NE": UNKNOWN, "-1": UNKNOWN, "-3": UNKNOWN})


def read_mapping(path):
    rows = []
    for raw in chunks(path):
        f = normalize(raw)
        # Alguns leiautes usam ANO_ELEICAO em vez de AA_ELEICAO.
        if "AA_ELEICAO" not in f and "ANO_ELEICAO" in f:
            f = f.rename(columns={"ANO_ELEICAO": "AA_ELEICAO"})
        f = scope(f, election=False)
        if "NR_TURNO" in f:
            f = f[f.NR_TURNO == "1"]
        require(f, LOCAL)
        for source, target in [("NM_BAIRRO", "Bairro"), ("NM_LOCAL_VOTACAO", "Escola")]:
            f[target] = clean_label(f[source]) if source in f else UNKNOWN
        rows.append(f[LOCAL + ["Bairro", "Escola"]].drop_duplicates())
    mapping = pd.concat(rows, ignore_index=True).drop_duplicates()
    conflicts = mapping.duplicated(LOCAL, keep=False)
    bad = mapping.loc[conflicts, LOCAL].drop_duplicates()
    bad["Bairro"], bad["Escola"] = UNKNOWN, UNKNOWN
    mapping = pd.concat([mapping.loc[~conflicts], bad], ignore_index=True)
    return mapping, len(bad)


def attach_mapping(votes, mapping=None):
    if mapping is None:
        result = votes.assign(Bairro=UNKNOWN, Escola=UNKNOWN)
    else:
        result = votes.merge(mapping, on=LOCAL, how="left", validate="many_to_one")
        result[["Bairro", "Escola"]] = result[["Bairro", "Escola"]].fillna(UNKNOWN)
    if "Escola_secoes" in result:
        # O próprio resultado eleitoral é fonte direta do nome do local.
        known = result.Escola_secoes.ne(UNKNOWN)
        result.loc[known, "Escola"] = result.loc[known, "Escola_secoes"]
    if len(result) != len(votes) or int(result.Votos.sum()) != int(votes.Votos.sum()):
        raise ValueError("O mapeamento alterou os totais.")
    return result


def read_totals(path, number, election):
    rows = []
    for raw in chunks(path):
        f = scope(normalize(raw))
        require(f, ZONE + ["NR_CANDIDATO", "QT_VOTOS_NOMINAIS"])
        f = f[(f.NR_CANDIDATO == number) & (f.CD_ELEICAO == election)].copy()
        f["Oficial"] = vote_int(f.QT_VOTOS_NOMINAIS)
        dimensions = [c for c in ["SQ_CANDIDATO", "ST_VOTO_EM_TRANSITO", "NM_TIPO_DESTINACAO_VOTOS"] if c in f]
        rows.append(f[ZONE + dimensions + ["Oficial"]])
    result = pd.concat(rows, ignore_index=True)
    identity = [c for c in result if c != "Oficial"]
    if result.duplicated(identity).any():
        raise ValueError("Totalização contém candidato/município/zona duplicado.")
    if result.empty:
        raise ValueError("Candidato/eleição ausente da totalização: não validado.")
    return result.groupby(ZONE, as_index=False).Oficial.sum()


def reconcile(votes, totals):
    actual = votes.groupby(ZONE, as_index=False).Votos.sum()
    check = actual.merge(totals, on=ZONE, how="outer").fillna(0)
    check[["Votos", "Oficial"]] = check[["Votos", "Oficial"]].astype("int64")
    check["Diferença"] = check.Votos - check.Oficial
    return check


def summary(frame, keys):
    table = frame.groupby(keys, as_index=False, dropna=False).Votos.sum()
    total = int(table.Votos.sum())
    table["Percentual"] = table.Votos / total * 100 if total else 0.0
    table["Posição"] = table.Votos.rank(method="min", ascending=False).astype(int)
    return table.sort_values(["Votos"] + keys, ascending=[False] + [True] * len(keys))


def csv_bytes(frame):
    safe = frame.copy()
    for col in safe.select_dtypes(include="object"):
        safe[col] = safe[col].map(lambda v: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v)
    return safe.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


def table_download(title, frame, name):
    st.subheader(title)
    st.dataframe(frame, hide_index=True, use_container_width=True)
    st.download_button("Baixar CSV — " + title, csv_bytes(frame), name + ".csv", "text/csv")


def existing(kind):
    for suffix in [".zip", ".csv"]:
        path = DATA / (kind + suffix)
        if path.exists():
            return path
    return None


@st.cache_data(show_spinner=False)
def load_cached(number, signature):
    paths = {k: Path(p) for k, p, _, _ in signature}
    votes, election, dates, found = read_votes(paths["secoes"], number)
    warnings, mapping = [], None
    if "locais" in paths:
        try:
            mapping, conflicts = read_mapping(paths["locais"])
            if conflicts:
                warnings.append(f"{conflicts} locais conflitantes: Não identificado.")
        except (ValueError, OSError, zipfile.BadZipFile) as exc:
            warnings.append("Mapeamento indisponível: " + str(exc))
    else:
        warnings.append("Arquivo de locais ausente; bairros não identificados. Escolas são exibidas apenas quando constam no resultado eleitoral.")
    votes = attach_mapping(votes, mapping)
    check = None
    if "totais" in paths:
        try:
            check = reconcile(votes, read_totals(paths["totais"], number, election))
        except (ValueError, OSError, zipfile.BadZipFile) as exc:
            warnings.append("Total oficial não validado: " + str(exc))
    return votes, check, dates, found, warnings


def main():
    st.set_page_config(page_title="Votos por bairro • SP 2026", page_icon="🗳️", layout="wide")
    st.title("Votos por bairro · São Paulo")
    st.caption("Eleições 2026 · Deputado federal · Primeiro turno · Fonte: TSE")
    st.info("Bairro do local de votação, não de residência dos eleitores. Sem inferência por endereço ou nome de escola.")
    with st.sidebar:
        st.header("Consulta")
        number = st.text_input("Número do candidato (4 dígitos)", placeholder="Ex.: 3034").strip()
        st.caption("O número deve corresponder à candidatura de 2026. O app não presume a identidade da pessoa.")
        if st.button("Baixar / atualizar arquivos do TSE"):
            for kind in SOURCES:
                with st.spinner(f"Baixando {kind} — pode demorar vários minutos…"):
                    try:
                        download(kind)
                        st.success(f"{kind}: atualizado")
                    except (requests.RequestException, OSError, ValueError, zipfile.BadZipFile) as exc:
                        st.warning(f"{kind}: indisponível. {exc}")
            load_cached.clear()
        st.caption("Arquivos grandes. Também é possível colocar CSVs/ZIPs oficiais na pasta data; consulte o README.")
        for kind, url in PAGES.items():
            st.markdown(f"[Fonte TSE — {kind}]({url})")
    with st.expander("Fontes e rastreabilidade"):
        for kind in SOURCES:
            path = existing(kind)
            st.write(f"{kind}: {path.name if path else 'não disponível'}")
            if path and path.with_suffix(".json").exists():
                st.json(json.loads(path.with_suffix(".json").read_text(encoding="utf-8")))
            elif path:
                st.caption("Importação local: autenticidade e integridade do arquivo não certificadas pelo app.")
    if not existing("secoes"):
        st.warning("Resultados indisponíveis localmente. Baixe os arquivos oficiais para começar. Nenhum voto foi estimado.")
        return
    if not re.fullmatch(r"\d{4}", number):
        st.info("Informe um número de candidato com quatro dígitos.")
        return
    signature = tuple((k, str(p), p.stat().st_mtime_ns, p.stat().st_size)
                      for k in SOURCES if (p := existing(k)))
    try:
        with st.spinner("Lendo os dados oficiais em blocos…"):
            votes, check, dates, found, warnings = load_cached(number, signature)
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        st.error("Consulta bloqueada por inconsistência nos dados: " + str(exc))
        return
    for message in warnings:
        st.warning(message)
    st.caption("Data(s) de geração declarada(s) no arquivo de seções: " + (", ".join(dates) or "não informada"))
    if not found:
        st.warning("Número não encontrado no arquivo de votos deste recorte. Isso não comprova candidatura nem votação zero.")
        return
    if check is None:
        st.warning("Totais NÃO validados contra arquivo independente. Resultados abaixo são exploratórios.")
    elif check["Diferença"].ne(0).any():
        st.error("Divergência com a totalização oficial. Confira datas, versão e situação dos votos. Não considere os totais conciliados.")
    else:
        st.success("Totais conciliados com o arquivo nominal em todas as combinações de município e zona.")
    if check is not None:
        with st.expander("Conferência de totais por município/zona"):
            table_download("Validação", check, f"{number}_validacao")
    total = int(votes.Votos.sum())
    unknown = int(votes.loc[votes.Bairro == UNKNOWN, "Votos"].sum())
    cols = st.columns(3)
    cols[0].metric("Votos no arquivo de SP", f"{total:,}".replace(",", "."))
    cols[1].metric("Cidades no arquivo", votes.CD_MUNICIPIO.nunique())
    cols[2].metric("Votos sem bairro identificado", f"{unknown:,}".replace(",", "."))
    st.caption("Percentual = participação nos votos deste candidato no recorte da tabela. Posição = ordem dos territórios por votos do candidato, com empates; não é classificação entre candidatos. Votos de legenda, brancos e nulos não entram.")
    cities = summary(votes, ["CD_MUNICIPIO", "NM_MUNICIPIO"])
    table_download("Cidades · percentual dos votos do candidato em SP", cities, f"{number}_cidades")
    labels = dict(zip(cities.CD_MUNICIPIO, cities.NM_MUNICIPIO))
    city = st.selectbox("Selecione uma cidade", cities.CD_MUNICIPIO.tolist(), format_func=lambda x: f"{labels[x]} ({x})")
    local = votes[votes.CD_MUNICIPIO == city]
    neighborhoods = summary(local, ["Bairro"])
    if int(neighborhoods.Votos.sum()) != int(local.Votos.sum()):
        st.error("Falha de conservação de votos nos bairros.")
        return
    table_download("Bairros · percentual dos votos do candidato na cidade", neighborhoods, f"{number}_{city}_bairros")
    neighborhood = st.selectbox("Detalhar bairro", ["Todos"] + neighborhoods.Bairro.tolist())
    detail = local if neighborhood == "Todos" else local[local.Bairro == neighborhood]
    schools = summary(detail, ["Bairro", "NR_ZONA", "NR_LOCAL_VOTACAO", "Escola"])
    table_download("Escolas / locais · percentual no recorte selecionado", schools, f"{number}_{city}_escolas")
    table_download("Seções · percentual no recorte selecionado", summary(detail, SECTION + ["Bairro", "NR_LOCAL_VOTACAO", "Escola"]), f"{number}_{city}_secoes")
    st.caption("Seções presentes no arquivo, mas sem registro para o número consultado, recebem zero. Seções ausentes do arquivo não são criadas. Nomes de bairros são preservados como informados pelo TSE.")


if __name__ == "__main__":
    main()
