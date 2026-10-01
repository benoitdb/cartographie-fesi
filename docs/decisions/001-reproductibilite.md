# ADR 001 — Reproductibilité des dépendances, images et Actions

**Date :** 2026-10-01
**Statut :** accepté — issue #200

## Contexte

Avant cette décision, les trois familles de composants externes n'avaient pas le
même niveau de verrouillage :

- dépendances Python déclarées en versions minimales (`pandas>=2.0.0`), sans
  lockfile : deux installations à un mois d'écart pouvaient différer ;
- images Docker désignées par tag, dont `metabase/metabase:latest` ;
- Actions GitHub désignées par tag majeur (`actions/checkout@v4`), qu'un
  mainteneur, ou un attaquant, peut déplacer sur un autre commit.

## Objectifs

1. Un même commit installe les mêmes composants, en local, en CI et sur
   Streamlit Community Cloud.
2. Une mise à jour est un diff explicite, relu et validé par la CI avant fusion.
3. Les mises à jour de sécurité restent praticables : elles arrivent seules, en
   PR, sans travail manuel de veille.

## Décision

- **Python** : les dépendances directes vivent dans `requirements/*.in`. Les
  fichiers installés sont générés par `pip-compile` (pip-tools), entièrement
  épinglés et hashés. Ils ne s'éditent jamais à la main.
- **Docker** : chaque image garde un tag lisible et versionné, suivi de son
  digest multi-architectures (`postgres:16-alpine@sha256:…`). Le digest fait
  foi ; le tag dit ce qu'on a voulu.
- **Actions GitHub** : SHA complet du commit, suivi d'un commentaire donnant la
  version (`# v4.4.0`).
- **Maintenance** : Dependabot ouvre chaque semaine des PR pour pip,
  docker-compose, npm et Actions. Chaque PR passe la CI avant fusion.

## Périmètre

| Source (`requirements/`) | Lockfile généré | Environnement |
|---|---|---|
| `dashboard.in` | `requirements.txt` | dashboard local, Streamlit Cloud |
| `pipeline.in` | `data-pipeline/requirements.txt` | pipeline de données |
| `dev.in` (dashboard + pipeline + outils de test) | `requirements-dev.txt` | tests, CI `tests` et `verify-metabase` |
| `dbt.in` | `requirements-dbt.txt` | couche dbt, CI `equivalence-dbt` |
| `dagster.in` (pipeline + dbt + Dagster) | `requirements-dagster.txt` | orchestration |
| `pip-tools.in` | `requirements/pip-tools.txt` | outil de verrouillage lui-même |

Images : `metabase/docker-compose.yml` (PostgreSQL, serveur GeoJSON, Metabase)
et l'image de service PostgreSQL de `.github/workflows/ci.yml`. Actions : tout
`.github/workflows/`.

## Mise à jour

1. Modifier le fichier `.in` concerné (ou accepter une PR Dependabot).
2. Installer pip-tools depuis son propre lockfile :
   `venv/bin/pip install --require-hashes -r requirements/pip-tools.txt`.
3. Lancer `./outils.sh verrouiller-dependances`. Sans `--upgrade`, pip-compile
   conserve les versions déjà épinglées et n'ajoute que ce qui manque ; pour
   monter une version, `venv/bin/pip-compile --upgrade-package <paquet> …`.
4. Relire le diff des lockfiles, puis laisser la CI trancher.

Pour une image : relever le digest de l'index multi-architectures du nouveau tag
et remplacer tag et digest ensemble.

## Limites connues

- **Résolution en Python 3.11**, la version de la CI et du venv local. Un
  environnement sur une autre version peut demander un paquet conditionnel
  absent du lockfile ; Streamlit Cloud est à contrôler au premier redéploiement.
- **Image de service de la CI** : Dependabot ne suit pas les images déclarées
  sous `services:` dans un workflow. Son digest se met à jour à la main, en même
  temps que celui de `metabase/docker-compose.yml`.
- **`data-pipeline/requirements.txt`** est compilé depuis un `.in` situé à la
  racine. Il faudra constater, au premier passage de Dependabot, qu'il est bien
  régénéré avec les autres.
- **Monter le digest d'une image Metabase** applique ses migrations à la base
  applicative (`metabase_pgdata`) au prochain démarrage : ce n'est pas réversible
  sans sauvegarde.

## Conséquences

Les mises à jour sont explicites et révisables : un même commit résout les mêmes
versions partout, et toute montée de version laisse une trace dans le diff. En
contrepartie, rien ne monte de version tout seul : une PR Dependabot laissée
sans suite est un correctif de sécurité non appliqué.
