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
