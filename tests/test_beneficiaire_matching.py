"""Rapprochement approché de noms de bénéficiaires (issue #23).

Deux erreurs symétriques, toutes deux silencieuses :
- rapprocher deux bénéficiaires réellement distincts (ex. deux communes
  homonymes) fait apparaître un regroupement qui n'existe pas ;
- ne pas rapprocher deux écritures du même bénéficiaire le fait disparaître des
  analyses de concentration.

Les seuils (SCORE_CUTOFF, SEUIL_MOT) ont été calés sur des cas réels : ces tests
les figent pour qu'un ajustement futur ne les déplace pas sans qu'on le voie.
"""

from beneficiaire_matching import build_fuzzy_clusters, normalize_nom


def test_normalize_retire_accents_ponctuation_et_forme_juridique():
    assert normalize_nom("Société d'Économie Mixte, SAS") == "SOCIETE D ECONOMIE MIXTE"


def test_normalize_est_insensible_a_la_casse_et_aux_espaces_multiples():
    assert normalize_nom("commune   de  Thônes") == normalize_nom("COMMUNE DE THONES")


def test_deux_ecritures_du_meme_beneficiaire_sont_regroupees():
    """Accent manquant d'une région à l'autre : c'est exactement le cas que
    l'égalité stricte du dashboard ne peut pas capter."""
    clusters = build_fuzzy_clusters(
        {
            "Commune de Thônes": {"Auvergne-Rhône-Alpes"},
            "COMMUNE DE THONES": {"Bretagne"},
        }
    )

    assert len(set(clusters.values())) == 1
    assert len(clusters) == 2


def test_deux_communes_differentes_ne_sont_pas_regroupees():
    clusters = build_fuzzy_clusters(
        {
            "Commune de Toulouse": {"Occitanie"},
            "Commune de Toulon": {"Provence-Alpes-Côte d'Azur"},
        }
    )

    assert clusters == {}


def test_la_verification_mot_a_mot_rattrape_ce_que_le_score_laisse_passer():
    """Le test précédent passe en réalité grâce au seuil de score : « Commune de
    Toulouse » et « Commune de Toulon » sont à 88,9, juste sous SCORE_CUTOFF=90.
    Il ne prouve donc rien sur la vérification mot à mot, qui est pourtant le vrai
    garde-fou du module.

    On abaisse ici le seuil à 80 pour placer la paire au-dessus du score : si
    seule la similarité globale décidait, ces deux communes seraient regroupées.
    C'est le résidu « TOULOUSE » / « TOULON », inexplicable par une variante de
    saisie, qui doit les séparer."""
    clusters = build_fuzzy_clusters(
        {
            "Commune de Toulouse": {"Occitanie"},
            "Commune de Toulon": {"Provence-Alpes-Côte d'Azur"},
        },
        score_cutoff=80,
    )

    assert clusters == {}


def test_deux_noms_proches_dans_la_meme_region_ne_sont_pas_regroupes():
    """Restriction volontaire aux régions disjointes : l'intra-région est déjà
    couvert par le rapprochement exact du dashboard, le refaire ici produirait
    des doublons de signalement."""
    clusters = build_fuzzy_clusters(
        {
            "Commune de Thônes": {"Auvergne-Rhône-Alpes"},
            "COMMUNE DE THONES": {"Auvergne-Rhône-Alpes"},
        }
    )

    assert clusters == {}


def test_un_beneficiaire_sans_variante_n_est_pas_signale():
    """Les singletons ne sont pas des regroupements : les inclure noierait les
    vrais cas."""
    clusters = build_fuzzy_clusters(
        {
            "Commune de Thônes": {"Auvergne-Rhône-Alpes"},
            "Université de Bretagne": {"Bretagne"},
        }
    )

    assert clusters == {}


def test_les_variantes_en_chaine_forment_un_seul_cluster():
    """Transitivité de l'union-find : A~B et B~C donnent {A, B, C}, pas deux
    clusters qui se chevauchent."""
    clusters = build_fuzzy_clusters(
        {
            "Commune de Thônes": {"Auvergne-Rhône-Alpes"},
            "COMMUNE DE THONES": {"Bretagne"},
            "Commune de Thones": {"Normandie"},
        }
    )

    assert len(clusters) == 3
    assert len(set(clusters.values())) == 1


def test_la_forme_juridique_presente_d_un_seul_cote_n_empeche_pas_le_rapprochement():
    """Le même bénéficiaire saisi avec puis sans sa forme juridique est un cas
    courant du fichier source. Sans le retrait opéré par normalize_nom, le mot
    surnuméraire ferait chuter le score et ferait manquer le rapprochement."""
    clusters = build_fuzzy_clusters(
        {
            "Association Les Amis du Parc": {"Bretagne"},
            "Les Amis du Parc": {"Normandie"},
        }
    )

    assert len(clusters) == 2
    assert len(set(clusters.values())) == 1
