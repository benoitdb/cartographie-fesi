"""Provisionne les rôles PostgreSQL locaux, sans journaliser de secret."""

import configuration


def transferer_propriete_public(cur, proprietaire, sql_module):
    """Transfère au compte Metabase les objets applicatifs du schéma public.

    Les objets système ne sont jamais concernés : la requête est limitée au
    schéma ``public`` de la base interne Metabase. La migration est idempotente,
    car les objets déjà détenus par ``proprietaire`` ne sont pas sélectionnés.
    """
    cur.execute(
        """
        SELECT c.relkind, c.relname
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'S', 'v', 'm')
          AND (
              c.relkind <> 'S'
              OR NOT EXISTS (
                  SELECT 1
                  FROM pg_depend AS d
                  WHERE d.classid = 'pg_class'::regclass
                    AND d.objid = c.oid
                    AND d.deptype IN ('a', 'i')
              )
          )
          AND c.relowner <> (SELECT oid FROM pg_roles WHERE rolname = %s)
        ORDER BY c.relkind, c.relname
        """,
        (proprietaire,),
    )
    commandes = {
        "r": "TABLE",
        "p": "TABLE",
        "S": "SEQUENCE",
        "v": "VIEW",
        "m": "MATERIALIZED VIEW",
    }
    for kind, name in cur.fetchall():
        cur.execute(
            sql_module.SQL("ALTER {} {} OWNER TO {}").format(
                sql_module.SQL(commandes[kind]),
                sql_module.Identifier(name),
                sql_module.Identifier(proprietaire),
            )
        )
    cur.execute(
        sql_module.SQL("ALTER SCHEMA public OWNER TO {}").format(sql_module.Identifier(proprietaire))
    )


def main():
    import psycopg2
    from psycopg2 import sql

    env = configuration.charger_env()
    admin, password, database = configuration.exiger(env, "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
    with psycopg2.connect(host="localhost", port=int(env.get("POSTGRES_PORT", "5437")), dbname=database, user=admin, password=password) as conn, conn.cursor() as cur:
        for prefix in ("METABASE_APP", "FESI_LOADER", "FESI_READER"):
            user, secret = configuration.exiger(env, f"{prefix}_USER", f"{prefix}_PASSWORD")
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
            if cur.fetchone():
                cur.execute(sql.SQL("ALTER ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT").format(sql.Identifier(user)), (secret,))
            else:
                cur.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT").format(sql.Identifier(user)), (secret,))
        app = env["METABASE_APP_USER"]
        cur.execute(sql.SQL("ALTER DATABASE metabase OWNER TO {}").format(sql.Identifier(app)))
        loader, reader = env["FESI_LOADER_USER"], env["FESI_READER_USER"]
        cur.execute("REVOKE CONNECT ON DATABASE fesi FROM PUBLIC")
        cur.execute(sql.SQL("GRANT CONNECT ON DATABASE fesi TO {}, {}").format(sql.Identifier(loader), sql.Identifier(reader)))
        cur.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}, {}").format(sql.Identifier(loader), sql.Identifier(reader)))
        cur.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(loader)))
        cur.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(sql.Identifier(loader)))
        cur.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(reader)))
    with psycopg2.connect(host="localhost", port=int(env.get("POSTGRES_PORT", "5437")), dbname="metabase", user=admin, password=password) as conn, conn.cursor() as cur:
        transferer_propriete_public(cur, env["METABASE_APP_USER"], sql)
    print("OK : rôles techniques provisionnés.")


if __name__ == "__main__":
    main()
