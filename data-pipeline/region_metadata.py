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

from reference.cohesion_ue import REGION_CATEGORIE_UE, REGION_ULTRAPERIPHERIQUE

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
            "ultraperipherique": region in REGION_ULTRAPERIPHERIQUE,
        }
        print(f"  {region}: {population:,} hab. ({population_year}), {area} km², {capital}".replace(",", " "))

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"✅ Écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
