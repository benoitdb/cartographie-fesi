# ADR 001 — Reproductibilité des dépendances, images et Actions

**Date :** 2026-10-01
**Statut :** accepté — issue #200

## Décision

- Les dépendances Python directes vivent dans `requirements/*.in` ; les fichiers
  utilisés par les environnements sont générés par `pip-compile`, épinglés et hashés.
- Les images Docker gardent leur tag et ajoutent un digest multi-architectures.
- Les Actions GitHub utilisent un SHA complet, documenté par un commentaire de tag.
- Dependabot ouvre chaque semaine des PR pour pip, npm, Docker et Actions.

## Mise à jour

1. Modifier le fichier `.in` concerné.
2. Installer `pip-tools` depuis son lockfile, puis lancer
   `./outils.sh verrouiller-dependances`.
3. Vérifier le diff et la CI avant fusion.

## Conséquences

Les mises à jour sont explicites et révisables. Un même commit résout les mêmes
