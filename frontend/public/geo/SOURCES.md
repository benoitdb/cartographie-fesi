# Sources des contours géographiques

- `regions-metropole.geojson`, `departements.geojson` : contours IGN (licence Etalab Open License),
  via le dépôt open source [france-geojson](https://github.com/gregoiredavid/france-geojson).
- `regions-dromcom.geojson` : Guadeloupe, Martinique, Guyane, La Réunion, Mayotte — même source
  `france-geojson` (`regions.geojson`), même précision/format que `regions-metropole.geojson`.
  Saint-Martin (collectivité d'outre-mer, pas une région — absente des découpages INSEE/IGN
  utilisés par `france-geojson`, qui ne couvre que les DROM) provient d'une source distincte :
  [Natural Earth](https://www.naturalearthdata.com/) 1:10m Admin 0 – Map Units (domaine public),
  entité `ADM0_A3 = MAF` — une résolution plus généraliste (frontières mondiales) que le reste du
  fichier, donc un contour un peu moins fin, mais c'est la seule source trouvée en session qui
  isole spécifiquement Saint-Martin (partie française) du reste des Antilles.
- `dromcom_codes_postaux.json` : centroïdes commune(s) par code postal, pour les 6 territoires
  DROM-COM — extrait filtré (préfixes 971/972/973/974/976) du jeu de données
  [Communes de France - Base des codes postaux](https://www.data.gouv.fr/datasets/communes-de-france-base-des-codes-postaux)
  (data.gouv.fr, export La Poste/INSEE, récupéré 2026-08-15 ; le CSV complet France entière
  n'est pas conservé dans le repo, seul cet extrait DROM-COM). Un code postal couvrant plusieurs
  communes (8% des cas, ex. `97218` = Grand'Rivière/Macouba/Basse-Pointe) est résolu par la
  moyenne de leurs coordonnées — écart négligeable à l'échelle d'une carte de territoire.
  **Saint-Martin (97150) absent du dataset** (latitude/longitude vides pour cette entrée dans le
  CSV source, même trou que pour `regions-dromcom.geojson`) — sourcé séparément : Marigot
  (chef-lieu), Wikidata [Q200605](https://www.wikidata.org/wiki/Q200605), 18.0731° N, -63.0822° O.
