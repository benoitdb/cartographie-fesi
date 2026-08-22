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

## Elle est auto-cohérente

Ses blocs `aggregates` et `metadata` sont **recalculés sur l'échantillon**, par
le même code que le pipeline (`data-pipeline/agregats.py`) — un total lu dans la
fixture décrit donc bien ses 413 opérations. C'est ce qui autorise une assertion
sur une valeur, ce que la version précédente interdisait : elle reprenait le
bloc `aggregates` du fichier complet, décrivant 16 625 opérations
([issue #60](https://github.com/benoitdb/cartographie-fesi/issues/60), levée par
l'extraction du calcul hors d'`ingest.py`).

`test_la_fixture_est_auto_coherente` le vérifie à chaque exécution : chaque
opération compte dans exactement une partition, et la somme par fonds couvre
tout le périmètre.

**Ce qu'elle ne prouve toujours pas** : les tests de fumée n'attrapent que
l'exception, pas l'allure des pages. Une vérification visuelle reste nécessaire
sur tout changement d'affichage.

## Contenu

| Fichier | Origine |
|---|---|
| `data.json` | 413 opérations : 20 par région (les 3 fonds représentés) + les 13 interrégionales, trop rares pour survivre à un échantillonnage par région alors que le dashboard lit `aggregates["interregional"]` sans valeur par défaut. `aggregates` et `metadata` recalculés dessus. Le champ `Objectifs et réalisations escomptés et effectifs` est tronqué à 200 caractères : il pèse 61,5 % du fichier réel et n'est lu nulle part dans `dashboard/`. |
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
