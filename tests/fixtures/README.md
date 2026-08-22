# Fixture de test du dashboard

Échantillon de données réelles permettant aux tests de fumée du dashboard
(`tests/test_dashboard_pages.py`) de tourner **sur un clone nu**, donc en CI.
Régénérée par `generer_fixture.py`.

## Pourquoi des données réelles ici, et pourquoi ce n'est pas généralisable

La liste des opérations FEDER / FSE+ / FTJ est une **publication officielle
ouverte** de l'État, sans donnée à caractère personnel au sens du RGPD :
committer un extrait est légitime.

**Ne pas reconduire ce raisonnement par analogie.** Un fichier de forme
comparable — mêmes colonnes, même origine administrative — peut relever d'un
régime tout autre ; la liste des bénéficiaires de la PAC en est l'exemple. Pour
toute future fixture issue de données réelles, le caractère personnel
s'**investigue avant**, il ne se suppose pas. À défaut : fixture synthétique ou
sous-ensemble anonymisé.

## Ce que la fixture n'est pas

**Elle ne sert pas à des assertions sur des valeurs.** Le bloc `aggregates` de
`data.json` est repris **tel quel** du fichier complet : il décrit les 16 625
opérations, pas les 400 de l'échantillon. Un test qui comparerait un total
affiché à un total attendu serait donc faux — et le champ
`metadata.fixture` le rappelle dans le fichier lui-même.

Rendre la fixture auto-cohérente supposerait de rejouer le calcul d'agrégats,
qui est aujourd'hui écrit à plat dans `data-pipeline/ingest.py` et n'est pas
réutilisable ([issue #60](https://github.com/benoitdb/cartographie-fesi/issues/60)).

## Contenu

| Fichier | Origine |
|---|---|
| `data.json` | 400 opérations (20 par région, les 3 fonds représentés) + `aggregates` complet. Le champ `Objectifs et réalisations escomptés et effectifs` est tronqué à 200 caractères : il pèse 61,5 % du fichier réel et n'est lu nulle part dans `dashboard/`. |
| `beneficiaires_fuzzy.json` | copie intégrale (8 Ko) |
| `transferts_solidarite.json` | copie intégrale (< 1 Ko) |

## Entretien

À régénérer **quand le schéma de `data.json` change** (colonne ajoutée,
renommée, supprimée) : sans cela, les tests de fumée valideraient le dashboard
contre un schéma périmé, ce qui est précisément le silence qu'ils doivent
éliminer.

```
venv/bin/python tests/fixtures/generer_fixture.py
```
