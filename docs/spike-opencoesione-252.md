# Spike #252 — Parcours Metabase et benchmark OpenCoesione

**Relevé du 5 novembre 2026 — étude en cours.** Ce document distingue les
constats API, la lecture du code et les essais visuels. La comparaison Kohesio
reste à compléter ; la structure proposée ci-dessous reste à arbitrer.

## Périmètre et décisions

- [#252](https://github.com/benoitdb/cartographie-fesi/issues/252) : capacités
  constatées de Metabase, benchmark OpenCoesione et comparaison Kohesio, puis
  proposition de structure à arbitrer. Aucune implémentation des écrans.
- Ordre validé : #252, puis #238 (compte de démonstration), puis #124
  (recherche et détail des opérations).
- Les issues transverses #8 (DuckDB) et #10 (positionnement) ne conditionnent
  pas ce lot. Les profils de consultation servent à expliquer les parcours ;
  ils n'imposent pas de variantes du contenu par audience.
- Toute proposition d'écran s'appuie sur les marts dbt (ADR 002). Les
  requêtes existantes ne valent pas autorisation de créer une couche SQL parallèle.

## État effectif de l'instance

Les trois conteneurs existants ont été redémarrés sans recréation ni mise à
jour. `GET /api/health` répond `{"status":"ok"}`. Ce contrôle prouve seulement
que le service répond.

`GET /api/session/properties` indique **v0.64.2.7**, hash `682919c`, date de
version `2026-10-15`. La référence `origin/main` utilisée pour la branche
d'étude est `5816b08` (elle prévoit v0.64.2.8) ; la PR Dependabot #253 propose
une autre version, non utilisée pour cette étude.

L'inventaire API authentifié confirme la collection FESI et ses tableaux :
Accueil (8), Territoires (10), Structure & répartition (11), Pilotage (12),
Analyses & contrôle (13), Qualité des sources (14). Les identifiants ci-dessous
sont ceux de cette instance, pas des constantes du produit.

### Géographie : configuration non alignée avec le code

`GET /api/setting/custom-geojson` contient `fesi_metropole` seulement. Son URL
pointe encore vers `main/frontend/public/geo/regions-metropole.geojson`, alors
que le code actuel épingle une révision. `fesi_dromcom` est absent, bien que
la question 107 « Engagé — Carte DROM-COM » le demande.

La lecture de `ensure_geojson_map()` explique pourquoi une relance ne suffit
pas : la fonction retourne dès que `fesi_metropole` existe, sans réconcilier
son URL ni vérifier la présence de l'autre carte. Constat suivi en
[#256](https://github.com/benoitdb/cartographie-fesi/issues/256). Aucun réglage
géographique n'a été modifié pendant cet inventaire. Le rendu reste à vérifier.

### Questions et filtres existants

La lecture de `GET /api/card/{id}` confirme :

| Question | Source SQL | Filtres déclarés |
|---|---|---|
| 84 — Montant UE | `marts.engage_all` | période, périmètre, fonds |
| 86 — Par fonds | `marts.engage_all` | période, périmètre, fonds |
| 88 — Carte des régions | `marts.engage_all` | période, fonds |
| 95 — Hiérarchie thématique | `marts.repartition_all` | période, périmètre, fonds |
| 107 — Carte DROM-COM | `marts.engage_all` | période, fonds |

Les réglages de clic des cartes du tableau ne sont pas configurés dans les
définitions relues. Cela ne prouve ni la présence ni l'absence de possibilités
de navigation par défaut : elles doivent être exercées dans l'interface.

## Capacités constatées — essais reproductibles

Deux tableaux ont été dupliqués avec leurs questions, exclusivement pour les
sondes : 15 « SPIKE 252 — Interactions temporaires » et 16 « SPIKE 252 — Cartes
temporaires ». Le rendu a été observé dans le navigateur en largeur bureau
(les commandes d'édition étaient masquées dans le volet étroit initial).

| Fonction | Verdict sur v0.64.2.7 | Essai et limite |
|---|---|---|
| Barre → filtre de dashboard | **Possible après configuration** | Copier Structure ; éditer la carte « Par fonds » ; Comportement au clic → Mettre à jour un filtre → colonne `fonds` vers filtre Fonds ; sauvegarder. Un clic FEDER inscrit `fonds=FEDER` dans l'URL et fait passer le compteur de 16 625 à 6 038. Effacer le filtre rétablit l'ensemble. Par défaut, le clic montrait seulement la valeur et l'action Copier. |
| Région GeoJSON → filtre Périmètre | **Possible après configuration** | Sur la copie Territoires, carte temporaire métropole, colonne `region` vers filtre Périmètre. Le clic Bretagne inscrit le filtre ; les KPI deviennent 194 962 203,70 € et 767 opérations (2021-2027, tous fonds). La carte d'ensemble reste entière, car elle ignore volontairement ce filtre. |
| Treemap à deux niveaux | **Possible, zoom interne observé** | Copie Structure → Hiérarchie, sans filtre Fonds/Périmètre, 2021-2027. Cliquer une tuile ESO4.8 ouvre son groupe « Europe plus sociale » avec un retour au parent. L'URL et les filtres restent inchangés : ce zoom n'est pas un filtre croisé des autres cartes. Le filtre croisé thématique n'a pas été configuré ni vérifié. |
| GeoJSON métropole | **Possible** | La copie de la question 88 utilise un fond temporaire épinglé sur l'URL déjà prévue dans le code. Les 13 régions métropolitaines sont dessinées et le clic est exercé. Le défaut de l'instance FESI d'origine est une configuration périmée (#256), pas une incapacité du moteur. |
| DROM-COM sur un même fond | **Rendu possible, lisibilité insuffisante dans la mise en page essayée** | La copie de la question 107 rend le fond temporaire contenant les six territoires. Le cadrage global les réduit à de très petites formes. Aucun équivalent aux encarts Streamlit n'est prouvé par cet essai. Des vues séparées restent une piste à tester, pas une capacité déclarée acquise. |
| Région → question enregistrée avec filtres | **Possible avec navigation explicite** | Comportement au clic → Destination personnalisée → question 127 ; passer `region` à Périmètre et le filtre courant Fonds à Fonds. En 2014-2020/FSE, clic Bretagne : l'URL cible porte les deux valeurs et la liste affiche les sept opérations attendues. Sonde technique bornée à 50 lignes, pas implémentation de #124. |
| Drill-through automatique d'un résultat SQL vers les opérations | **Absent sur les cartes SQL essayées** | Le clic par défaut sur la barre et sur un numéro d'opération de la liste ne proposait que Copier la valeur. Il faut prévoir une question cible et une navigation explicite ; ne pas supposer que Metabase reconstruit la provenance d'un agrégat SQL. Ce constat ne porte pas sur les questions construites dans l'éditeur graphique. |
| Fiche narrative complète | **Non vérifiée** | La liste technique n'a que numéro, périmètre, fonds et montant. Elle ne prouve ni la gestion d'un résumé long, ni le rendu d'une fiche #124. |
| Field filter sur une table aliasée | **Échec reproduit dans la configuration actuelle** | Deux questions temporaires identiques sur `marts.engage_all`, filtre Fonds=FEDER : sans alias, une ligne et statut completed ; avec `FROM marts.engage_all e`, erreur PostgreSQL « invalid reference to FROM-clause entry ». Il s'agit du comportement des tags actuels, pas d'une impossibilité universelle de gérer les alias. |

### Deux précautions supplémentaires découvertes

- La destination « question enregistrée » a utilisé l'hôte configuré
  `localhost`, alors que la session était ouverte sur `127.0.0.1`. Le clic a
  donc abouti à une nouvelle connexion. La même destination ouverte sur
  `127.0.0.1` a conservé la session et affiché les sept lignes filtrées. Le
  filtre est transmis ; le parcours sans rupture demande un hôte cohérent.
  Aucun réglage global de site n'a été modifié pour masquer ce constat.
- L'ajout temporaire d'un fond via le nom court du service GeoJSON local a
  été refusé (HTTP 400, validation d'URL). Les essais ont utilisé à la place
  les URL publiques épinglées prévues par le projet, sans modifier la protection.
  Un PUT partiel du dashboard a aussi échoué ; le format complet du script
  du projet (paramètres, onglets, cartes) a été accepté puis relu.

## Sources du benchmark OpenCoesione

L'accès automatique aux deux portails a renvoyé 403 le 5 novembre 2026.
L'utilisateur a fourni les pages OpenCoesione enregistrées et leurs captures :

- accueil : `OpenCoesione - Home.html` ;
- exploration : `OpenCoesione - Browse cohesion projects data.html` ;
- résultats : `OpenCoesione - Projects list.html` ;
- fiche : `OpenCoesione - D27H12001840009---FSCRI_RI_3412---688887367.html` ;
- cinq captures de l'exploration/liste et deux captures de la fiche.

Ces fichiers ont été lus localement ; ils ne sont pas recopiés dans le dépôt.
Les captures régionales portent sur le Piémont ; les captures nationales et
la fiche affichent une mise à jour au 31 août 2026. C'est la date affichée par
la source ; notre observation est du 5 novembre 2026. Aucun chiffre italien
n'est utilisé comme référence de calcul pour FESI.

### Ce que la structure apporte

| Élément observé | Intérêt pour FESI | Transposition proposée et preuve/limite |
|---|---|---|
| Navigation séparant explication de la politique et exploration des données | Le lecteur comprend où consulter et où approfondir | Une entrée principale d'exploration, des liens distincts vers méthodologie et analyses. Les liens d'accueil et onglets existent déjà sur l'instance. |
| Bandeau de contexte puis indicateurs immédiatement visibles | Le lecteur sait quel territoire et quelle période expliquent les chiffres | Période unique explicite, territoire et fonds visibles, puis montant UE engagé, nombre d'opérations et millésime. Reprendre les dotations/estimations avec leurs réserves, sans les assimiler aux paiements italiens. |
| Thèmes à gauche, carte à droite, questions courtes sous les titres | Deux entrées complémentaires vers le même ensemble | Treemap et carte réutilisent `repartition_all` et `engage_all`. Les clics carte/barre sont prouvés ; le zoom interne du treemap a un sens différent à expliquer. |
| Même grammaire nationale et régionale | Descendre dans le détail ne demande pas de réapprendre l'écran | Garder la même structure avec Périmètre. Le passage à la liste conserve ce contexte via une navigation explicite. |
| Classements, programmes et trajectoire après la vue synthétique | L'approfondissement vient après la première compréhension | Réutiliser les écrans existants de pilotage/répartition ; conserver les limites de dates de #152 et la provenance des montants de #136. |
| Bouton vers la liste de projets, filtres actifs et facettes latérales | Le résultat global mène à des dossiers concrets | Proposer « Voir les opérations » avec contexte conservé. Une liste Metabase avec paramètres est faisable ; la présentation exacte en cartes riches et les facettes à compteurs ne sont pas prouvées. |
| Résultats avec titre, identifiant, territoire, thème et mesures distinctes | Choisir un projet sans ouvrir chaque fiche | Table lisible et colonnes choisies pour #124 ; ne pas promettre une copie exacte des cartes HTML italiennes. |
| Fiche avec identité, millésime, financement, avancement, acteurs et territoire | Un ordre de lecture stable et explicite | Réutiliser l'ordre pour les champs réellement disponibles. La fiche narrative et le résumé long restent à éprouver dans #124. |
| Valeurs absentes affichées explicitement dans la fiche | L'absence de donnée ne devient pas une fausse précision | Dates manquantes annoncées, sans déduire un état d'avancement de la date de fin. |
| Téléchargements et projets apparentés en fin de parcours | L'exploration peut se poursuivre hors de l'écran | Le téléchargement de la liste technique est visible. Exports de fiche et rapprochements constituent des options futures, pas un prérequis du premier lot. |

### Ce qu'il faut adapter aux données françaises

OpenCoesione dispose de paiements, d'un état d'avancement et d'une nature
d'investissement qui ne sont pas des champs équivalents des schémas FESI
actuellement exploités. Les dépenses éligibles ne sont pas des paiements ;
un taux engagé/dotation n'est pas un avancement physique. Ces blocs ne se
copient pas avec des libellés approchants.

Le sélecteur italien autorise toutes les périodes ensemble. FESI doit garder
une période explicite : les cadres 2014-2020 et 2021-2027, leurs thèmes et leurs
dates ne sont pas interchangeables. L'ensemble national doit aussi conserver
les programmes nationaux et interrégionaux que la carte ne peut pas localiser.

Les cartes communales et les indicateurs socio-économiques externes visibles
sur le Piémont demanderaient d'autres données et des dénominateurs fiables.
Ils ne sont pas des changements de mise en page à inclure implicitement.

## Proposition de structure — à arbitrer

L'utilisateur apprécie la présentation générale d'OpenCoesione et souhaite
ajouter ensuite les éléments Streamlit manquants, notamment statistiques,
au cas par cas. La proposition porte donc d'abord sur le parcours principal :

1. **Explorer les financements** : contexte période/périmètre/fonds, millésime
   et réserves courtes ; KPI ; thèmes et carte ; répartition par fonds ;
   accès au pilotage ; lien visible vers les opérations filtrées.
2. **Consulter les opérations** (#124) : recherche bénéficiaire/intitulé,
   filtres adaptés à la période, nombre de résultats et table ; accès au détail.
3. **Lire une opération** (#124) : identité et source, description, montants
   distincts, dates disponibles, territoire, programme/thème et réserves.
4. **Approfondir** : accès aux analyses statistiques, au pilotage détaillé et
   à la qualité des sources déjà présents. Les compléments Streamlit se
   décident un par un, avec une preuve de faisabilité et de compréhension.

Recommandation d'interaction : un clic sur la carte sélectionne le territoire,
puis un lien explicite ouvre les opérations avec les mêmes filtres. Un clic
sur une tuile du treemap peut rester un zoom thématique interne. Ne pas donner
au même geste un sens imprévisible selon le graphique. Le choix d'un lien
contextuel unique et la conservation de tous les filtres restent à valider
sur le futur écran : la sonde n'a éprouvé qu'une liste 2014-2020.

Cette proposition réorganise l'entrée dans l'outil ; elle ne décide ni de
supprimer les cinq dashboards existants, ni d'abandonner leurs analyses.
L'adoption de la structure exacte appartient à l'utilisateur.

### Besoins en données de #124, pas implémentés ici

Les marts agrégés ne portent pas toutes les informations d'une fiche. Le
mart `perimetre_2014_2020` permet une liste technique, mais pas le titre, le
bénéficiaire, le résumé et toute la provenance. Le mart de cofinancement
2021-2027 filtre certains dossiers : il ne convient pas comme liste exhaustive.

#124 devra définir un mart de consultation au niveau opération, avec la
fusion correcte de chaque période et une identité dont l'unicité est vérifiée.
Ne pas supposer que le numéro d'opération seul est une clé globale entre
sources et périodes. Une modification du modèle se fera dans dbt, pas dans
une vue SQL parallèle ni dans des règles réécrites au niveau des cartes.

## Comparaison Kohesio et suite

Le second point de comparaison reste à compléter à partir des pages et
captures récupérées manuellement. Aucun constat d'interface Kohesio n'est
inféré de sa seule réputation ou du 403.

La fiche narrative Metabase, le filtre croisé thématique et une présentation
DROM-COM lisible ne sont pas déclarés validés. Les sondes expliquent ce qui
est faisable et les points à concevoir, sans remplacer le travail de #124.

**#252 reste ouverte** jusqu'à la fin du relevé, de la comparaison et de
l'arbitrage.

## Rangement des sondes

Les deux tableaux et leurs 19 questions temporaires ont été archivés de façon
réversible après les essais. Avant action, les identifiants ont été comparés
aux 49 questions référencées par les autres tableaux : aucune question partagée.
La séparation a été recontrôlée juste avant l'archivage ; chaque état `archived`
a ensuite été relu. Les réglages GeoJSON initiaux ont été restaurés et comparés
à la sauvegarde prise avant les ajouts. Le défaut de #256 reste donc présent
sur l'instance d'origine ; aucune correction produit n'est livrée par cette étude.
