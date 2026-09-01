CREATE DATABASE metabase;

CREATE TABLE operations (
    id SERIAL PRIMARY KEY,
    periode TEXT NOT NULL,
    numero_operation TEXT,
    numcci TEXT,
    libelle_programme TEXT,
    intitule_projet TEXT,
    nom_beneficiaire TEXT,
    cp_beneficiaire TEXT,
    cp_operation TEXT,
    zone TEXT,
    departement TEXT,
    region_source TEXT,
    region TEXT,
    pays TEXT,
    fonds TEXT NOT NULL,
    objectif_strategique TEXT,
    objectif_specifique TEXT,
    objectif_specifique_code TEXT,
    type_intervention TEXT,
    depenses_eligibles NUMERIC,
    taux_cofinancement NUMERIC,
    montant_ue NUMERIC,
    date_premiere_convention DATE,
    date_debut DATE,
    date_fin DATE,
    is_interregional BOOLEAN DEFAULT FALSE,
    is_national BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_operations_region ON operations(region);
CREATE INDEX idx_operations_fonds ON operations(fonds);
CREATE INDEX idx_operations_periode ON operations(periode);
CREATE INDEX idx_operations_region_fonds ON operations(region, fonds);

CREATE TABLE programme_totals (
    id SERIAL PRIMARY KEY,
    periode TEXT NOT NULL,
    region TEXT NOT NULL,
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
