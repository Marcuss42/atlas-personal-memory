import sqlite3
from pathlib import Path

DB = Path("data/atlas.db")

if not DB.exists():
    print(f"Banco não encontrado: {DB.resolve()}")
    raise SystemExit(1)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("=" * 80)
print("ATLAS - INSPEÇÃO DO BANCO")
print("=" * 80)
print(f"Banco: {DB.resolve()}")

# ---------------------------------------------------------------------
# 1. Tabelas
# ---------------------------------------------------------------------

tables = conn.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
      AND name NOT LIKE 'sqlite_%'
    ORDER BY name
""").fetchall()

print("\nTABELAS:")
for row in tables:
    print(f"  - {row['name']}")

# ---------------------------------------------------------------------
# 2. Estrutura das tabelas
# ---------------------------------------------------------------------

for row in tables:
    table = row["name"]

    print("\n" + "-" * 80)
    print(f"TABELA: {table}")
    print("-" * 80)

    columns = conn.execute(f'PRAGMA table_info("{table}")').fetchall()

    for col in columns:
        print(
            f"  {col['name']:<25} "
            f"type={str(col['type']):<15} "
            f"pk={col['pk']}"
        )

# ---------------------------------------------------------------------
# 3. Procurar Servidor-001 até Servidor-006 em TODAS as tabelas
# ---------------------------------------------------------------------

print("\n" + "=" * 80)
print("BUSCANDO SERVIDORES")
print("=" * 80)

servidores = [f"Servidor-{i:03d}" for i in range(1, 7)]

for servidor in servidores:
    print("\n" + "#" * 80)
    print(f"{servidor}")
    print("#" * 80)

    encontrou = False

    for row in tables:
        table = row["name"]

        columns = conn.execute(
            f'PRAGMA table_info("{table}")'
        ).fetchall()

        text_columns = [
            col["name"]
            for col in columns
            if col["type"] is None
            or "CHAR" in str(col["type"]).upper()
            or "TEXT" in str(col["type"]).upper()
            or "CLOB" in str(col["type"]).upper()
        ]

        if not text_columns:
            continue

        for column in text_columns:
            try:
                rows = conn.execute(
                    f'''
                    SELECT *
                    FROM "{table}"
                    WHERE "{column}" = ?
                       OR "{column}" LIKE ?
                    LIMIT 20
                    ''',
                    (servidor, f"%{servidor}%")
                ).fetchall()

                if rows:
                    encontrou = True

                    print(f"\nTabela: {table}")
                    print(f"Coluna: {column}")

                    for result in rows:
                        print(dict(result))

            except Exception as e:
                print(
                    f"Erro consultando {table}.{column}: {e}"
                )

    if not encontrou:
        print("  >>> NÃO ENCONTRADO")

# ---------------------------------------------------------------------
# 4. Conteúdo específico das tabelas importantes
# ---------------------------------------------------------------------

for table in ["entities", "memory_items", "relations", "messages"]:
    exists = conn.execute("""
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
    """, (table,)).fetchone()

    if not exists:
        continue

    print("\n" + "=" * 80)
    print(f"TABELA {table} - REGISTROS RELACIONADOS A SERVIDOR")
    print("=" * 80)

    columns = conn.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()

    searchable = [
        col["name"]
        for col in columns
        if col["type"] is None
        or "CHAR" in str(col["type"]).upper()
        or "TEXT" in str(col["type"]).upper()
        or "CLOB" in str(col["type"]).upper()
    ]

    if not searchable:
        print("Nenhuma coluna textual.")
        continue

    conditions = []
    params = []

    for column in searchable:
        conditions.append(f'"{column}" LIKE ?')
        params.append("%Servidor-%")

    sql = f'''
        SELECT *
        FROM "{table}"
        WHERE {" OR ".join(conditions)}
        LIMIT 100
    '''

    try:
        rows = conn.execute(sql, params).fetchall()

        if not rows:
            print("Nenhum registro.")
        else:
            for result in rows:
                print(dict(result)) 
    except Exception as e:
        print(f"Erro consultando {table}: {e}")


conn.close()

print("\n" + "=" * 80)
print("FIM DA INSPEÇÃO")
print("=" * 80)