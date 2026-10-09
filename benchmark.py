"""Medição reproduzível com 200 mil registros SINTÉTICOS, sem rede."""
import json
import tempfile
from pathlib import Path
from time import perf_counter
import pandas as pd
import app


def main():
    work = Path.cwd() / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as directory:
        path = Path(directory) / "sintetico.csv"
        n = 200_000
        frame = pd.DataFrame({"NR_SECAO": [str(i % 2000 + 1) for i in range(n)],
                              "NR_VOTAVEL": [str(1000 + i // 2000) for i in range(n)]})
        for key, value in dict(ANO_ELEICAO="2026", SG_UF="SP", CD_CARGO="6", NR_TURNO="1",
                               CD_ELEICAO="999", CD_MUNICIPIO="1", NM_MUNICIPIO="TESTE",
                               NR_ZONA="1", NR_LOCAL_VOTACAO="10", QT_VOTOS="2").items():
            frame[key] = value
        frame.to_csv(path, sep=";", index=False)
        start = perf_counter()
        expected = app.read_votes(path, "1001")[0]
        baseline = perf_counter() - start
        start = perf_counter()
        app.read_votes_indexed(path, "1000")
        cold = perf_counter() - start
        start = perf_counter()
        actual = app.read_votes_indexed(path, "1001")[0]
        warm = perf_counter() - start
        pd.testing.assert_frame_equal(expected, actual)
        print(json.dumps({"registros_sinteticos": n, "leitura_anterior_segundos": round(baseline, 3),
                          "preparacao_e_primeira_consulta_segundos": round(cold, 3),
                          "outro_candidato_base_pronta_segundos": round(warm, 3),
                          "aceleracao_consulta": round(baseline / warm, 1),
                          "resultados_identicos": True}, indent=2))


if __name__ == "__main__":
    main()
