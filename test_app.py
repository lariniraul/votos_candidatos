"""Testes com dados exclusivamente sintéticos; nenhum resultado eleitoral real."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
import app


def fixture():
    base = dict(ANO_ELEICAO="2026", NR_TURNO="1", CD_ELEICAO="999",
                SG_UF="SP", CD_CARGO="6", CD_MUNICIPIO="71072",
                NM_MUNICIPIO="CIDADE TESTE", NR_ZONA="1", NR_LOCAL_VOTACAO="10")
    return pd.DataFrame([dict(base, NR_SECAO="1", NR_VOTAVEL="1234", QT_VOTOS="10"),
                         dict(base, NR_SECAO="2", NR_VOTAVEL="1234", QT_VOTOS="20"),
                         dict(base, NR_SECAO="3", NR_VOTAVEL="5678", QT_VOTOS="30")])


class DataTests(unittest.TestCase):
    def test_preparation_only_selected_cargo_and_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture().to_csv(root / "secoes.csv", sep=";", index=False)
            fixture().assign(CD_CARGO="1", NR_VOTAVEL="11").to_csv(root / "secoes_presidente.csv", sep=";", index=False)
            with patch.object(app, "DATA", root):
                ready, errors, stamp = app.prepare_cargo("6", fetch=False)
                self.assertIn(("secoes", False), ready)
                self.assertNotIn(("secoes_presidente", True), ready)
                self.assertEqual(len(list((root / "indices").glob("*.sqlite"))), 1)
                self.assertTrue(errors)  # Optional sources absent, no fabricated mapping.
                with patch.object(app, "chunks", side_effect=AssertionError("Não deve reler")):
                    ready2, _, stamp2 = app.prepare_cargo("6", fetch=False)
                self.assertEqual(ready, ready2)
                self.assertEqual(stamp, stamp2)
                app.prepare_cargo("1", fetch=False)
                self.assertEqual(len(list((root / "indices").glob("*.sqlite"))), 2)

    def test_index_matches_original_and_reuses_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "votes.csv"
            fixture().to_csv(path, sep=";", index=False)
            expected = app.read_votes(path, "1234")
            actual = app.read_votes_indexed(path, "1234")
            pd.testing.assert_frame_equal(expected[0], actual[0])
            self.assertEqual(expected[1:], actual[1:])
            with patch.object(app, "chunks", side_effect=AssertionError("Não deve reler CSV")):
                self.assertEqual(app.read_votes_indexed(path, "5678")[0].Votos.sum(), 30)
            fixture().assign(QT_VOTOS="100").to_csv(path, sep=";", index=False)
            self.assertEqual(app.read_votes_indexed(path, "1234")[0].Votos.sum(), 200)

    def test_index_preserves_duplicate_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "votes.csv"
            pd.concat([fixture(), fixture()]).to_csv(path, sep=";", index=False)
            with self.assertRaisesRegex(ValueError, "duplicados"):
                app.read_votes_indexed(path, "1234")

    def test_indexed_totals_match_and_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "totals.csv"
            fixture().iloc[[0]].assign(NR_CANDIDATO="1234", QT_VOTOS_NOMINAIS="30").to_csv(path, sep=";", index=False)
            expected = app.read_totals(path, "1234", "999")
            actual = app.read_totals(path, "1234", "999", indexed=True)
            pd.testing.assert_frame_equal(expected, actual)
            with patch.object(app, "chunks", side_effect=AssertionError("Não deve reler CSV")):
                pd.testing.assert_frame_equal(actual, app.read_totals(path, "1234", "999", indexed=True))

    def test_each_office_and_turn_filters(self):
        for label, (cargo, digits) in app.CARGOS.items():
            number = "1" * digits
            good = fixture().iloc[[0]].assign(CD_CARGO=cargo, NR_VOTAVEL=number)
            mixed = pd.concat([good, good.assign(SG_UF="RJ"), good.assign(NR_TURNO="2"),
                               good.assign(CD_CARGO="99")])
            with patch.object(app, "chunks", return_value=iter([mixed])):
                result = app.read_votes(Path("unused"), number, cargo)[0]
            self.assertEqual(result.Votos.sum(), 10, label)
            self.assertTrue(app.valid_number(number, digits))
            self.assertFalse(app.valid_number(number + "0", digits))

    def test_presidential_zip_uses_br_and_filters_sp(self):
        import zipfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "totais.zip"
            base = fixture().iloc[[0]].assign(CD_CARGO="1", NR_CANDIDATO="11", QT_VOTOS_NOMINAIS="10")
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("totais_SP.csv", base.assign(CD_CARGO="6").to_csv(index=False, sep=";"))
                z.writestr("totais_BR.csv", pd.concat([base, base.assign(SG_UF="RJ")]).to_csv(index=False, sep=";"))
            self.assertEqual(app.read_totals(path, "11", "999", "1").Oficial.sum(), 10)

    def test_president_second_turn(self):
        f = fixture().iloc[[0]].assign(CD_CARGO="1", NR_VOTAVEL="11", NR_TURNO="2")
        with patch.object(app, "chunks", return_value=iter([f])):
            self.assertEqual(app.read_votes(Path("unused"), "11", "1", "2")[0].Votos.sum(), 10)

    def read(self, frame):
        with patch.object(app, "chunks", return_value=iter([frame])):
            return app.read_votes(Path("unused"), "1234")

    def test_filter_and_zero(self):
        f = fixture()
        wrong = f.iloc[[0]].assign(SG_UF="RJ")
        result, election, _, found = self.read(pd.concat([f, wrong]))
        self.assertEqual(result.Votos.tolist(), [10, 20, 0])
        self.assertEqual(election, "999")
        self.assertTrue(found)

    def test_duplicate_blocked_across_chunks(self):
        with patch.object(app, "chunks", return_value=iter([fixture(), fixture()])):
            with self.assertRaisesRegex(ValueError, "duplicados"):
                app.read_votes(Path("unused"), "1234")

    def test_negative_blocked(self):
        with self.assertRaises(ValueError):
            self.read(fixture().assign(QT_VOTOS="-1"))

    def test_mixed_election_blocked(self):
        with self.assertRaises(ValueError):
            self.read(pd.concat([fixture(), fixture().assign(CD_ELEICAO="998")]))

    def test_missing_column_blocked(self):
        with self.assertRaisesRegex(ValueError, "Colunas"):
            self.read(fixture().drop(columns="NR_ZONA"))

    def test_mapping_conflict_unknown_without_multiplication(self):
        f = pd.DataFrame([dict(AA_ELEICAO="2026", SG_UF="SP", CD_MUNICIPIO="71072",
                              NR_ZONA="1", NR_LOCAL_VOTACAO="10", NM_BAIRRO=b,
                              NM_LOCAL_VOTACAO="ESCOLA TESTE") for b in ["CENTRO", "CENTRO", "OUTRO"]])
        with patch.object(app, "chunks", return_value=iter([f])):
            mapping, conflicts = app.read_mapping(Path("unused"))
        result = app.attach_mapping(self.read(fixture())[0], mapping)
        self.assertEqual(conflicts, 1)
        self.assertEqual(result.Votos.sum(), 30)
        self.assertTrue(result.Bairro.eq(app.UNKNOWN).all())

    def test_missing_mapping_preserves_votes(self):
        result = app.attach_mapping(self.read(fixture())[0])
        self.assertEqual(result.Votos.sum(), 30)
        self.assertTrue(result.Bairro.eq(app.UNKNOWN).all())

    def test_percentages_ties_and_zero(self):
        f = pd.DataFrame({"Bairro": ["A", "B", "C"], "Votos": [10, 10, 0]})
        result = app.summary(f, ["Bairro"])
        self.assertEqual(result["Posição"].tolist(), [1, 1, 3])
        self.assertEqual(result.Percentual.sum(), 100)
        self.assertEqual(app.summary(f.assign(Votos=0), ["Bairro"]).Percentual.sum(), 0)

    def test_reconciliation_detects_offsetting_errors(self):
        votes = pd.DataFrame({"CD_MUNICIPIO": ["1", "1"], "NR_ZONA": ["1", "2"], "Votos": [10, 20]})
        totals = pd.DataFrame({"CD_MUNICIPIO": ["1", "1"], "NR_ZONA": ["1", "2"], "Oficial": [20, 10]})
        result = app.reconcile(votes, totals)
        self.assertEqual(result["Diferença"].tolist(), [-10, 10])

    def test_csv_roundtrip_and_formula(self):
        data = app.csv_bytes(pd.DataFrame({"Bairro": ["=1+1", "São José"], "Votos": [1, 2]}))
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        self.assertIn("'=1+1", data.decode("utf-8-sig"))

    def test_zip_reader_sp_only(self):
        import zipfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("test_SP.csv", fixture().to_csv(index=False, sep=";"))
                z.writestr("test_BRASIL.csv", fixture().to_csv(index=False, sep=";"))
            result = app.read_votes(path, "1234")[0]
            self.assertEqual(result.Votos.sum(), 30)

    def test_streamlit_empty_state(self):
        at = AppTest.from_file(str(Path(app.__file__))).run()
        self.assertFalse(at.exception)
        self.assertIn("Votos por bairro", at.title[0].value)
        self.assertEqual(len(at.button), 4)
        self.assertEqual(len(at.text_input), 0)
        self.assertEqual(len(at.dataframe), 0)

    def test_streamlit_populated_flow(self):
        # Use an isolated copy so fixture files cannot be mistaken for live data.
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(app.__file__, root / "app.py")
            (root / "data").mkdir()
            fixture().to_csv(root / "data" / "secoes.csv", sep=";", index=False, encoding="latin-1")
            at = AppTest.from_file(str(root / "app.py")).run()
            with patch("requests.get", side_effect=app.requests.ConnectionError("Teste offline")):
                at.button(key="cargo_6").click().run(timeout=20)
            at.text_input[0].set_value("1234").run()
            self.assertFalse(at.exception)
            self.assertEqual(len(at.dataframe), 4)
            self.assertEqual(at.metric[0].value, "30")
            next(s for s in at.selectbox if s.label == "Detalhar bairro").select(app.UNKNOWN).run()
            self.assertFalse(at.exception)

    def test_menu_switches_offices(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(app.__file__, root / "app.py")
            (root / "data").mkdir()
            frames = [fixture().iloc[[0]].assign(CD_CARGO=c, NR_VOTAVEL="1" * d)
                      for c, d in app.CARGOS.values()]
            data = pd.concat(frames)
            for name in ["secoes", "secoes_presidente"]:
                data.to_csv(root / "data" / (name + ".csv"), sep=";", index=False, encoding="latin-1")
            at = AppTest.from_file(str(root / "app.py")).run()
            for label, (cargo, digits) in app.CARGOS.items():
                with patch("requests.get", side_effect=app.requests.ConnectionError("Teste offline")):
                    at.button(key=f"cargo_{cargo}").click().run(timeout=20)
                at.text_input(key=f"numero_{cargo}").set_value("1" * digits).run()
                self.assertFalse(at.exception)
                self.assertEqual(at.metric[0].value, "10")
                self.assertEqual(len(at.dataframe), 4)
            # Returning to a prepared office must neither download nor rebuild it.
            with patch("requests.get", side_effect=AssertionError("Não deve baixar")):
                at.button(key="cargo_6").click().run()
            self.assertFalse(at.exception)
            self.assertEqual(at.text_input(key="numero_6").value, "1111")

    def test_index_contains_only_clicked_office(self):
        import sqlite3
        from contextlib import closing
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "votes.csv"
            pd.concat([fixture(), fixture().assign(CD_CARGO="7")]).to_csv(path, sep=";", index=False)
            database = app.prepare_index(path, "votes", cargo="6")
            with closing(sqlite3.connect(database)) as conn:
                self.assertEqual(conn.execute("SELECT DISTINCT CD_CARGO FROM records").fetchall(), [("6",)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
