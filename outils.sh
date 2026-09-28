#!/usr/bin/env bash
# Point d'entrée unique des outils locaux, un port fixe par outil (issue #188).
#
# Tous liés à 127.0.0.1 : rien n'est joignable depuis le réseau local. Les
# ports sont définis ICI et nulle part ailleurs, à deux exceptions près, qui
# doivent rester alignées sur ce fichier :
#   - metabase/docker-compose.yml (3000, 5437), lu par Docker ;
#   - dbt/profiles.yml et dbt/verifier_vues_postgres.py (5437).
#
#   ./outils.sh ports       # la table des ports, et ce qui écoute déjà
#   ./outils.sh dashboard   # Streamlit
#   ./outils.sh metabase    # stack Docker Metabase + PostgreSQL
#   ./outils.sh dbt-docs    # graphe et documentation des modèles dbt
#   ./outils.sh duckdb-ui   # carnet SQL sur dbt/target/fesi.duckdb
#   ./outils.sh dagster     # graphe d'assets et exécutions (spike #183)
#
# Registre transverse (tous projets) : ../docs/ports-locaux.md

set -euo pipefail

HOTE=127.0.0.1
PORT_METABASE=3000
PORT_DAGSTER=3001
PORT_DUCKDB_UI=4213
PORT_POSTGRES=5437
PORT_DBT_DOCS=8081
PORT_DASHBOARD=8501

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ports() {
    printf '%-6s %-12s %s\n' PORT OUTIL "ÉTAT"
    local ligne port outil
    for ligne in \
        "$PORT_METABASE metabase" "$PORT_DAGSTER dagster" "$PORT_DUCKDB_UI duckdb-ui" \
        "$PORT_POSTGRES postgres" "$PORT_DBT_DOCS dbt-docs" "$PORT_DASHBOARD dashboard"; do
        read -r port outil <<<"$ligne"
        if ss -ltn "sport = :$port" 2>/dev/null | grep -q LISTEN; then
            printf '%-6s %-12s %s\n' "$port" "$outil" "écoute"
        else
            printf '%-6s %-12s %s\n' "$port" "$outil" "-"
        fi
    done
}

# Refuse de démarrer sur un port déjà pris : sans ça, Streamlit et dbt docs
# glissent en silence sur le port suivant, et « un outil par port » ne tient plus.
port_libre() {
    if ss -ltn "sport = :$1" 2>/dev/null | grep -q LISTEN; then
        echo "Port $1 déjà occupé ($2 tourne peut-être déjà) : ./outils.sh ports" >&2
        exit 1
    fi
}

case "${1:-}" in
    ports)
        ports
        ;;
    dashboard)
        port_libre "$PORT_DASHBOARD" dashboard
        cd "$RACINE/dashboard"
        exec venv/bin/streamlit run Accueil.py \
            --server.address "$HOTE" --server.port "$PORT_DASHBOARD"
        ;;
    metabase)
        port_libre "$PORT_METABASE" metabase
        cd "$RACINE/metabase"
        docker compose up -d
        echo "Metabase : http://$HOTE:$PORT_METABASE  —  PostgreSQL : $HOTE:$PORT_POSTGRES"
        ;;
    dbt-docs)
        port_libre "$PORT_DBT_DOCS" dbt-docs
        cd "$RACINE/dbt"
        venv/bin/dbt docs generate --profiles-dir .
        exec venv/bin/dbt docs serve --profiles-dir . --host "$HOTE" --port "$PORT_DBT_DOCS"
        ;;
    duckdb-ui)
        port_libre "$PORT_DUCKDB_UI" duckdb-ui
        cd "$RACINE/dbt"
        # DuckDB est mono-écrivain : tant que ce carnet est ouvert, `dbt build` et
        # Dagster échouent sur le verrou du fichier. Le quitter avant un build.
        # L'interface est servie en local mais charge son code depuis
        # ui.duckdb.org (réglage ui_remote_url) : il faut le réseau.
        exec venv/bin/python -c "
import duckdb
c = duckdb.connect('target/fesi.duckdb')
c.sql('SET ui_local_port = $PORT_DUCKDB_UI')
c.sql('CALL start_ui()')
input('Carnet DuckDB sur http://localhost:$PORT_DUCKDB_UI — Entrée pour quitter et libérer le verrou. ')
"
        ;;
    dagster)
        port_libre "$PORT_DAGSTER" dagster
        if [[ ! -x "$RACINE/orchestration/venv/bin/dagster" ]]; then
            echo "orchestration/venv absent : voir le spike Dagster (#183, PR #185)." >&2
            exit 1
        fi
        cd "$RACINE/orchestration"
        DAGSTER_HOME="$PWD" exec venv/bin/dagster dev \
            -m fesi_orchestration.definitions -h "$HOTE" -p "$PORT_DAGSTER"
        ;;
    *)
        sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'
        exit 1
        ;;
esac
