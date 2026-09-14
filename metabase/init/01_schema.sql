CREATE DATABASE metabase;

-- Schéma "définitif" Phase 0 (issue #121). Colonnes = les clés internes déjà
-- harmonisées côté Python (data-pipeline/schema_source.py, dashboard/utils/periodes.py),
-- pas les libellés bruts d'un fichier source : chaque source 2014-2020 hors-Synergie
-- (Bretagne, Normandie, Nouvelle-Aquitaine, PON FSE) a ses propres noms de colonnes
-- (anglais, SIRET, lat/lon, AXE/OT/PI/OS...) qui n'existent pas ailleurs.
-- `extra` recueille ce qui est propre à une seule source plutôt que d'ajouter
-- des colonnes vides à 80% pour tout le monde — même principe que le reste du
-- projet ("pas d'abstraction au-delà de ce qui est utile, à ce stade").
CREATE TABLE operations (
    id SERIAL PRIMARY KEY,
    source_id TEXT NOT NULL,        -- clé de sources.SOURCES : '2021-2027-conventionnees',
                                     -- '2014-2020-synergie', '2014-2020-pon-fse',
                                     -- '2014-2020-bretagne-officiel', '2014-2020-normandie',
                                     -- '2014-2020-nouvelle-aquitaine', ...
    periode TEXT NOT NULL,          -- '2021-2027' | '2014-2020'

    numero_operation TEXT,
    numcci TEXT,
    libelle_programme TEXT,
    intitule_projet TEXT,
    resume_operation TEXT,
    nom_beneficiaire TEXT,

    cp_beneficiaire TEXT,
    cp_operation TEXT,
    zone TEXT,
    departement TEXT,
    region_source TEXT,             -- valeur brute avant harmonisation (colonne Région,
                                     -- souvent peu remplie en 2014-2020 — cf. CLAUDE.md)
    region TEXT,                    -- région moderne retenue (regions_modernes[0] si mono-région)
    regions_modernes TEXT[],        -- toutes les régions concernées (cas interrégional, #77)
    pays TEXT,

    fonds TEXT,                     -- nullable : 26 dossiers Normandie 2014-2020 sans fonds
                                     -- renseigné (gotcha connu, cf. CLAUDE.md / agregats.py)
    objectif_strategique TEXT,      -- 2021-2027 seulement
    objectif_specifique TEXT,       -- 2021-2027 seulement
    domaine_intervention TEXT,      -- 2014-2020 seulement (dimension thématique)
    type_intervention TEXT,         -- 2021-2027 seulement

    depenses_eligibles NUMERIC,
    taux_cofinancement NUMERIC,
    montant_ue NUMERIC,

    date_debut DATE,
    date_fin DATE,
    date_convention DATE,           -- 2021-2027 : date de référence de programmation
    date_programmation DATE,        -- 2014-2020 : date de référence de programmation

    is_interregional BOOLEAN NOT NULL DEFAULT FALSE,
    is_national BOOLEAN NOT NULL DEFAULT FALSE,

    extra JSONB                     -- champs propres à une source : siret, lat/lon,
                                     -- insee_operation (Bretagne officiel), axe/ot/pi/os et
                                     -- service_gestionnaire (PON FSE), territoire (Normandie/
                                     -- Nouvelle-Aquitaine), etc.
);

CREATE INDEX idx_operations_region ON operations(region);
CREATE INDEX idx_operations_fonds ON operations(fonds);
CREATE INDEX idx_operations_periode ON operations(periode);
CREATE INDEX idx_operations_source ON operations(source_id);
CREATE INDEX idx_operations_region_fonds ON operations(region, fonds);
CREATE INDEX idx_operations_regions_modernes ON operations USING GIN(regions_modernes);
CREATE INDEX idx_operations_extra ON operations USING GIN(extra);

-- Enveloppes programmées, par région (ou 'national' pour le Volet national) et
-- par fonds. Déjà générique entre périodes côté JSON : programme_totals.json
-- (2021-2027) et programme_totals_2014_2020.json (Accord 14-20 + maquettes
-- REACT-EU déjà fusionnées, cf. programme_totals_2014_2020.py) ont la même
-- forme {region: {fonds: montant}} — un seul chargeur suffit pour les deux.
CREATE TABLE programme_totals (
    id SERIAL PRIMARY KEY,
    periode TEXT NOT NULL,
    region TEXT NOT NULL,
    fonds TEXT NOT NULL,
    montant_ue NUMERIC NOT NULL
);

CREATE INDEX idx_programme_totals_periode_region ON programme_totals(periode, region);

-- Dotations programmées par objectif stratégique, national uniquement
-- (Tableau 8 de l'Accord 2021-2027, dotations_os.py) — 2014-2020 n'a pas
-- d'objectif stratégique (cf. CLAUDE.md), donc pas de ligne pour cette période.
CREATE TABLE dotations_os (
    id SERIAL PRIMARY KEY,
    periode TEXT NOT NULL DEFAULT '2021-2027',
    objectif_strategique TEXT NOT NULL,
    fonds TEXT NOT NULL,
    montant_ue NUMERIC NOT NULL
);

CREATE TABLE region_metadata (
    region TEXT PRIMARY KEY,
    population INTEGER,
    superficie_km2 NUMERIC,
    chef_lieu TEXT,
    categorie_ue TEXT,
    ultraperipherique BOOLEAN DEFAULT FALSE
);
