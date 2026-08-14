"""
Enrichissement des régions (population, superficie, chef-lieu) via Wikidata.

Script one-shot, exécuté manuellement (les données ne changent pas assez souvent
pour justifier un appel réseau à chaque régénération de data.json) : écrit
data/processed/region_metadata.json, lu ensuite par le dashboard sans dépendance
réseau. Relancer ce script périodiquement (une fois par an suffit) pour rafraîchir
la population.

QID Wikidata résolus manuellement (requête SPARQL filtrée sur les 19 régions
modernes de region_mapping.MODERN_REGIONS, désambiguïsées par le type
"région de France" / "collectivité d'outre-mer" pour Saint-Martin) :
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "region_metadata.json"

REGION_QID = {
    "Auvergne-Rhône-Alpes": "Q18338206",
    "Bourgogne-Franche-Comté": "Q18578267",
    "Bretagne": "Q12130",
    "Centre-Val de Loire": "Q13947",
    "Corse": "Q14112",
    "Grand Est": "Q18677983",
    "Hauts-de-France": "Q18677767",
    "Île-de-France": "Q13917",
    "Normandie": "Q18677875",
    "Nouvelle-Aquitaine": "Q18678082",
    "Occitanie": "Q18678265",
    "Pays de la Loire": "Q16994",
    "Provence-Alpes-Côte d'Azur": "Q15104",
    "Guadeloupe": "Q17012",
    "Martinique": "Q17054",
    "Guyane": "Q3769",
    "La Réunion": "Q17070",
    "Mayotte": "Q17063",
    "Saint-Martin": "Q126125",
}

# Catégorie de région au sens de la politique de cohésion UE 2021-2027 (détermine le taux
# de cofinancement FEDER/FSE+ : 85% moins développée, 60% transition, 50% plus développée).
# Source : Commission Implementing Decision (EU) 2021/1130, Annexes I/II/III (liste des
# régions NUTS2, au niveau des anciennes régions pré-2016 — voir note ci-dessous pour le
# seul cas où l'agrégation vers les régions modernes n'est pas univoque).
#
# Auvergne-Rhône-Alpes est un cas particulier : l'ancienne région Rhône-Alpes (Annexe III,
# plus développée) et l'ancienne région Auvergne (Annexe II, en transition) ont fusionné en
# une seule région moderne à cheval sur deux catégories — signalé explicitement plutôt que
# résolu arbitrairement vers l'une des deux.
#
# Saint-Martin n'apparaît dans aucune des trois annexes (hors périmètre NUTS pour ce
# classement) : catégorie laissée à None plutôt que devinée.
REGION_CATEGORIE_UE = {
    "Île-de-France": "plus développée",
    "Auvergne-Rhône-Alpes": "mixte (Rhône-Alpes : plus développée / Auvergne : en transition)",
    "Bourgogne-Franche-Comté": "en transition",
    "Bretagne": "en transition",
    "Centre-Val de Loire": "en transition",
    "Corse": "en transition",
    "Grand Est": "en transition",
    "Hauts-de-France": "en transition",
    "Normandie": "en transition",
    "Nouvelle-Aquitaine": "en transition",
    "Occitanie": "en transition",
    "Pays de la Loire": "en transition",
    "Provence-Alpes-Côte d'Azur": "en transition",
    "Martinique": "en transition",
    "Guadeloupe": "moins développée",
    "Guyane": "moins développée",
    "La Réunion": "moins développée",
    "Mayotte": "moins développée",
    "Saint-Martin": None,
}

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "CartographieFESI/1.0 (dashboard FESI ; contact: benoit.dejeandelabatie@gmail.com)"

QUERY = """
SELECT ?item ?pop ?popDate ?area ?capitalLabel WHERE {{
  VALUES ?item {{ {values} }}
  OPTIONAL {{
    ?item p:P1082 ?popStatement .
    ?popStatement ps:P1082 ?pop .
    OPTIONAL {{ ?popStatement pq:P585 ?popDate . }}
  }}
  OPTIONAL {{ ?item wdt:P2046 ?area . }}
  OPTIONAL {{ ?item wdt:P36 ?capital . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr". }}
}}
"""


def fetch_wikidata():
    values = " ".join(f"wd:{qid}" for qid in REGION_QID.values())
    query = QUERY.format(values=values)
    req = urllib.request.Request(
        SPARQL_ENDPOINT + "?" + urllib.parse.urlencode({"query": query}),
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def most_recent_population(bindings_for_item):
    dated = [b for b in bindings_for_item if "popDate" in b]
    if dated:
        best = max(dated, key=lambda b: b["popDate"]["value"])
    else:
        best = bindings_for_item[0] if bindings_for_item else None
    if best is None or "pop" not in best:
        return None, None
    return int(float(best["pop"]["value"])), best["popDate"]["value"][:4]


def main():
    print("🌐 Interrogation de Wikidata pour les 19 régions...")
    result = fetch_wikidata()

    by_qid = {}
    for b in result["results"]["bindings"]:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        by_qid.setdefault(qid, []).append(b)

    metadata = {}
    for region, qid in REGION_QID.items():
        bindings = by_qid.get(qid, [])
        population, population_year = most_recent_population(bindings)
        area = next((b["area"]["value"] for b in bindings if "area" in b), None)
        capital = next((b["capitalLabel"]["value"] for b in bindings if "capitalLabel" in b), None)

        metadata[region] = {
            "wikidata_id": qid,
            "population": population,
            "population_year": population_year,
            "superficie_km2": float(area) if area else None,
            "chef_lieu": capital,
            "categorie_ue": REGION_CATEGORIE_UE[region],
        }
        print(f"  {region}: {population:,} hab. ({population_year}), {area} km², {capital}".replace(",", " "))

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"✅ Écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
