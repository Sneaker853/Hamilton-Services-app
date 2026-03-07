import os
import tempfile

import psycopg2
from psycopg2 import sql

SRC_DSN = "postgresql://postgres:080770@localhost:5432/portfolio_db"
DST_DSN = "postgresql://portfolio_db_x0so_user:jjpVrTruDdNTrw27rPZfwWMmDGfjxZnK@dpg-d6lpmcdm5p6s73fh9bf0-a.ohio-postgres.render.com/portfolio_db_x0so"
TABLES = ["stocks", "price_history", "asset_metrics"]


def to_sql_type(data_type, udt_name, char_len, num_precision, num_scale):
    if data_type == "character varying":
        return f"varchar({char_len})" if char_len else "varchar"
    if data_type == "character":
        return f"char({char_len})" if char_len else "char"
    if data_type == "numeric":
        if num_precision and num_scale is not None:
            return f"numeric({num_precision},{num_scale})"
        if num_precision:
            return f"numeric({num_precision})"
        return "numeric"
    if data_type == "timestamp without time zone":
        return "timestamp"
    if data_type == "timestamp with time zone":
        return "timestamptz"
    if data_type == "ARRAY":
        return f"{udt_name[1:]}[]" if udt_name.startswith("_") else f"{udt_name}[]"
    if data_type == "USER-DEFINED":
        return udt_name
    return data_type


def main():
    src = psycopg2.connect(SRC_DSN)
    dst = psycopg2.connect(DST_DSN)
    src.autocommit = True
    dst.autocommit = True

    try:
        for table in TABLES:
            print(f"--- {table}: inspect source schema")
            with src.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name, data_type, udt_name, character_maximum_length,
                           numeric_precision, numeric_scale, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s
                    ORDER BY ordinal_position
                    """,
                    (table,),
                )
                columns = cur.fetchall()

                if not columns:
                    print(f"SKIP {table}: source table missing")
                    continue

                cur.execute(
                    """
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name=kcu.constraint_name
                     AND tc.table_schema=kcu.table_schema
                    WHERE tc.table_schema='public'
                      AND tc.table_name=%s
                      AND tc.constraint_type='PRIMARY KEY'
                    ORDER BY kcu.ordinal_position
                    """,
                    (table,),
                )
                primary_keys = [row[0] for row in cur.fetchall()]

            col_defs = []
            col_names = []
            for (
                col_name,
                data_type,
                udt_name,
                char_len,
                num_precision,
                num_scale,
                is_nullable,
                col_default,
            ) in columns:
                sql_type = to_sql_type(data_type, udt_name, char_len, num_precision, num_scale)
                piece = f'"{col_name}" {sql_type}'
                if col_default is not None:
                    default_text = str(col_default)
                    if not default_text.startswith("nextval("):
                        piece += f" DEFAULT {default_text}"
                if is_nullable == "NO":
                    piece += " NOT NULL"
                col_defs.append(piece)
                col_names.append(col_name)

            if primary_keys:
                pk_sql = ",".join([f'"{key}"' for key in primary_keys])
                col_defs.append(f"PRIMARY KEY ({pk_sql})")

            create_sql = f'CREATE TABLE IF NOT EXISTS public."{table}" ({", ".join(col_defs)})'

            with dst.cursor() as cur:
                print(f"--- {table}: ensure destination table")
                cur.execute(create_sql)
                cur.execute(sql.SQL("TRUNCATE TABLE public.{}").format(sql.Identifier(table)))

            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{table}.csv") as temp_file:
                temp_path = temp_file.name

            col_list = ", ".join([f'"{name}"' for name in col_names])

            with src.cursor() as cur:
                print(f"--- {table}: exporting source rows")
                with open(temp_path, "w", newline="", encoding="utf-8") as out_file:
                    cur.copy_expert(f'COPY public."{table}" ({col_list}) TO STDOUT WITH CSV', out_file)

            with dst.cursor() as cur:
                print(f"--- {table}: importing into destination")
                with open(temp_path, "r", newline="", encoding="utf-8") as in_file:
                    cur.copy_expert(f'COPY public."{table}" ({col_list}) FROM STDIN WITH CSV', in_file)
                cur.execute(sql.SQL("SELECT COUNT(*) FROM public.{}").format(sql.Identifier(table)))
                count = cur.fetchone()[0]
                print(f"--- {table}: destination rows = {count}")

            os.remove(temp_path)

        print("DONE: local -> render copy complete")
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()
