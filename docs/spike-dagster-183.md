# Spike Dagster — rapport et recommandation

Issue [#183](https://github.com/benoitdb/cartographie-fesi/issues/183). Branche
`spike/dagster-183`, partie de `main`. Réalisé le 2026-09-28, dans la borne
d'une journée.

**Recommandation : oui, mais limité à un outil local de visualisation et
d'exécution.** Pas de planification, pas de CI, pas de déploiement. La
généalogie complète XLSX → PostgreSQL est obtenue sans réécrire une ligne de
pipeline, et la fidélité est intacte. En revanche, Dagster ralentit la chaîne
de 40 %, ajoute un environnement de 888 Mo, et deux liens du graphe tiennent
par une déclaration manuelle qui peut se périmer sans bruit. Détail et
réserves plus bas.

## La question

> Dagster peut-il décrire le cycle complet, du XLSX jusqu'à PostgreSQL, comme
> une seule chaîne d'assets visible, sans alourdir le déploiement Streamlit ni
> réécrire la logique existante ?

Rappel du cadrage : les données changent ~5 fois par an. **L'ordonnancement
n'est pas le besoin**, la visibilité l'est.

## Ce qui a été construit

| | |
|---|---|
| Assets | 58 : 7 XLSX (externes), 7 ingestions, 7 référentiels (dont `region_metadata`, externe), 1 codegen, 35 nœuds dbt (29 modèles + 6 seeds), 1 chargement PostgreSQL |
| Job | `cycle_duckdb` : XLSX → Parquet → codegen → dbt (DuckDB), sans infra |
| Python du spike | 349 lignes (`definitions.py` 291, `verifier_fidelite.py` 58) |
| Environnement | un 5ᵉ venv, `requirements-dagster.txt` (Dagster 1.13, dagster-dbt), 888 Mo, 66 s d'installation |
| Scripts réécrits | **aucun** : chaque asset appelle le script existant en sous-process |

Lancer l'interface (3000 est Metabase, 8501/8502 les deux Streamlit) :

```
cd orchestration && DAGSTER_HOME=$PWD venv/bin/dagster dev -m fesi_orchestration.definitions -p 3001
```

## Les mesures fixées avant de coder

| Mesure | Résultat |
|---|---|
| Généalogie continue XLSX → Parquet → staging → marts | **Oui**, mais deux liens sont recousus à la main (voir plus bas) |
| Dagster hors de `dashboard/requirements.txt` | **Oui**, environnement séparé, comme dbt |
| Fidélité | **Intacte** : 12 fichiers réécrits, 0 écart de contenu ; 40 tests dbt verts ; `verifier_equivalence.py` vert sur la base produite (318 contrôles) |
| Verrou DuckDB | Pool de concurrence `duckdb_fesi` limité à 1 **entre runs Dagster** ; **sans effet** sur un client extérieur (constaté, voir plus bas) |
| Durée d'une exécution complète | Manuelle **54 s** ; Dagster séquentiel **76 s** (+40 %) ; Dagster parallèle **79 s** |
| Lignes ajoutées, dépendances | 349 lignes, 1 environnement, 3 paquets directs (`dagster`, `dagster-webserver`, `dagster-dbt`) |

## Fidélité : le critère de l'issue était mal posé

L'issue demandait `git diff --exit-code data/ dbt/` après une exécution. Ce
critère ne peut **jamais** être vert, même avec la chaîne manuelle : chaque
JSON porte son `metadata.generated_at`, et chaque Parquet la version de pyarrow
qui l'a écrit. Une régénération à contenu identique produit donc 11 à 12
fichiers « modifiés ».

D'où `orchestration/verifier_fidelite.py`, qui compare les **contenus** contre
`HEAD` : JSON sans horodatage, Parquet cellule à cellule. Vu échouer avant
d'être utilisé : une valeur altérée dans le Parquet normandie → `ÉCART`,
code retour 1.

Il sert au-delà du spike : c'est la vérification « régénérer et comparer au bit
près » que le `CLAUDE.md` demande sur tout changement de pipeline, mais
outillée, et sur les sept sources au lieu de `data.json` seul.

## Ce que le spike a trouvé en chemin

**1. Un script cassé depuis trois semaines** (issue #184). En chronométrant la
chaîne manuelle de référence, `beneficiaires_fuzzy.py` échoue : il lit
`data["operations"]`, qui n'existe plus dans `data.json` depuis le passage au
Parquet (PR #132). Rien ne le lance en CI. Au prochain millésime, les
regroupements de bénéficiaires n'auraient pas été recalculés. Le script est
volontairement absent du graphe tant que #184 est ouverte.

**2. Deux dépendances n'étaient écrites nulle part.**
- Le staging DuckDB lit les Parquet par `read_parquet(...)` et non par
  `source()`. **dbt ne connaît donc pas ce lien**, et `dagster-dbt`, qui lit le
  manifest, non plus : sans intervention, la généalogie s'arrête net au
  staging. C'est exactement la coupure que le spike devait mesurer.
- `generer.py` lit, en plus des Parquet, quatre JSON (`programme_totals`,
  `programme_totals_2014_2020`, `categories_ue_2014_2020`, `region_metadata`)
  d'où sortent les seeds. Écrit nulle part ailleurs que dans son code, trouvé en
  le relisant, et d'abord **oublié** dans le graphe.

Les deux sont recousus dans `TraducteurFesi` et dans les `deps` du codegen.

**3. Une dépendance déclarée qui n'existe pas.** Le `CLAUDE.md` dit « `ingest.py`
d'abord car les autres scripts en dépendent ». Faux pour les six scripts de
référentiels, qui dérivent de `data-pipeline/reference/` et ne lisent aucune
sortie d'`ingest.py`. Vrai seulement pour `beneficiaires_fuzzy.py`, celui qui
est cassé. Le graphe le montre en un coup d'œil. Le texte, lui, ne le montrait pas.

**4. La contention DuckDB, en conditions réelles.** Pendant le spike, une
interface DuckDB ouverte sur `dbt/target/fesi.duckdb` tenait le verrou.
Résultat : 14 étapes réussies, `modeles_dbt` en échec avec un message qui nomme
le PID fautif. Dagster **localise** l'échec, et c'est un vrai gain par rapport
à la chaîne manuelle, mais il **ne l'empêche pas** : le pool de concurrence ne
sérialise que les runs qu'il lance lui-même.

## La réserve qui reste, et elle est réelle

**Les deux raccords manuels peuvent se périmer sans bruit.** Si `generer.py`
se met à lire un cinquième JSON, ou si une source est ajoutée à `SOURCES` sans
son staging, le graphe **ment** : il affiche une généalogie complète qui ne
l'est plus, et rien ne rougit. C'est le même genre de risque que celui que
l'issue #125 a éliminé pour les règles métier, déplacé ici vers la
généalogie. Le graphe n'est donc pas une source de vérité, seulement un
dessin très bien renseigné.

La voie pour supprimer le premier raccord existe : déclarer les Parquet comme
`sources` dbt avec `external_location` (fonctionnalité de `dbt-duckdb`), pour
que le staging passe par `source()` et que dbt, donc Dagster, connaisse le lien
nativement. Cela touche `generer.py` et le point de fork DuckDB/PostgreSQL : un
chantier à part, pas un ajout au spike.

**Le coût en temps.** +22 s sur 54 s. dbt seul passe de 8,1 s à 16,5 s sous
`dagster-dbt`, qui suit chaque événement dbt. Le parallélisme n'aide pas : lancées
ensemble, les ingestions voient chacune leur durée à peu près doubler (Synergie
17 → 34 s), si bien que le chemin critique ne raccourcit pas. Cause probable :
la mémoire (6 Go disponibles, plusieurs lectures XLSX simultanées), non
vérifiée. À 5 exécutions par an, ce coût est sans importance pratique, mais il
contredit l'intuition qu'un orchestrateur « accélère ».

## Recommandation

**Garder Dagster comme outil local**, sur la branche fusionnée :

- **pour voir** : le graphe des 58 assets, les métadonnées de chaque
  matérialisation (nombre d'opérations, taille du Parquet), les tests dbt
  rattachés à leur modèle ;
- **pour exécuter** une régénération de millésime en un clic, avec un échec
  localisé au lieu d'une liste de commandes à relancer à la main ;
- **pour vérifier** : `verifier_fidelite.py` après chaque régénération.

**Ne pas** l'étendre à la planification (le besoin n'existe pas), à la CI
(`equivalence-dbt` fait déjà le travail en 39 s sans lui), ni au déploiement.

Conditions avant d'en faire la voie documentée de régénération :

1. corriger #184, puis ajouter `beneficiaires_fuzzy` au graphe ;
2. décider du raccord Parquet → staging : l'accepter en le documentant, ou
   ouvrir le chantier `external_location` ;
3. corriger la phrase fausse du `CLAUDE.md` sur l'ordre des scripts.

**Pour l'angle portfolio**, le résultat le plus parlant n'est pas le graphe, ce
sont les découvertes : trois dépendances mal connues et un script cassé,
trouvés en une journée **parce qu'il fallait tout déclarer**. L'argument est
qu'expliciter la chaîne a une valeur propre, indépendante de l'outil qui
l'exécute. C'est le même enseignement que celui de la couche dbt : brancher un
contrôle sur un environnement neuf a une valeur en soi.
