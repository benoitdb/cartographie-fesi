"""Le script de précalcul lit bien la sortie réelle d'`ingest.py` (issue #184).

`beneficiaires_fuzzy.py` a lu `data["operations"]` dans `data.json` pendant trois
semaines après que les opérations en étaient parties pour `data.parquet`
(PR #132) : `KeyError` au premier lancement, que rien ne voyait puisque aucun
test ne passait par `main()`. Ce test y passe, sur un Parquet construit avec
la forme exacte qu'écrit `ingest.py` — `regions_modernes` y relu comme un
`numpy.ndarray`, pas une liste.
"""

import json

import beneficiaires_fuzzy
import pandas as pd


def test_main_lit_le_parquet_et_rapproche_entre_regions(tmp_path, monkeypatch):
    parquet = tmp_path / "data.parquet"
    sortie = tmp_path / "beneficiaires_fuzzy.json"
    pd.DataFrame(
        {
            "Nom du bénéficiaire": ["Commune de Thônes", "COMMUNE DE THONES", None],
            "regions_modernes": [["Auvergne-Rhône-Alpes"], ["Bretagne"], ["Bretagne"]],
        }
    ).to_parquet(parquet, index=False)
    # Ce que produit `ingest.py` : un data.json SANS opérations.
    (tmp_path / "data.json").write_text(json.dumps({"metadata": {}, "aggregates": {}}))
    monkeypatch.setattr(beneficiaires_fuzzy, "DATA_PATH", parquet)
    monkeypatch.setattr(beneficiaires_fuzzy, "OUTPUT_PATH", sortie)

    beneficiaires_fuzzy.main()

    clusters = json.loads(sortie.read_text(encoding="utf-8"))
    assert set(clusters) == {"Commune de Thônes", "COMMUNE DE THONES"}
    assert len(set(clusters.values())) == 1
