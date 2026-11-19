"""Run one SQL file against the Compose database and print every result set, so the exact
output can be pasted into ANSWERS.md.  Also saves the output under docs/outputs/<file>.txt.

    .venv\\Scripts\\python.exe analysis\\run_sql.py sql\\02_q1_area_four_ways.sql

Statements are split on semicolons at line ends; EXPLAIN output comes back as rows of text and is
printed line by line, exactly as psql would show it."""
import re, sys, time
from pathlib import Path

import psycopg
from dbconf import read_env

ROOT = Path(__file__).resolve().parents[1]


def statements(sql_text: str):
    """Yield (comment_block, statement) pairs. A comment block is the -- lines right above a statement."""
    buf, comments = [], []
    for line in sql_text.splitlines():
        if line.strip().startswith("--") and not buf:
            comments.append(line.strip())
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                yield "\n".join(comments), stmt
            buf, comments = [], []
    if "".join(buf).strip():
        yield "\n".join(comments), "\n".join(buf).strip()


def main(path: str):
    env = read_env()
    sql_path = Path(path)
    out_dir = ROOT / "docs" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (sql_path.stem + ".txt")
    lines = []

    def emit(s=""):
        print(s)
        lines.append(s)

    emit(f"-- {sql_path.as_posix()}  run at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    with psycopg.connect(host="localhost", port=int(env.get("POSTGRES_PORT", "5434")), user=env["POSTGRES_USER"],
                         password=env["POSTGRES_PASSWORD"], dbname=env["POSTGRES_DB"], autocommit=True) as con:
        for comments, stmt in statements(sql_path.read_text(encoding="utf-8")):
            emit()
            if comments:
                emit(comments)
            emit(stmt)
            t0 = time.perf_counter()
            with con.cursor() as cur:
                cur.execute(stmt)
                dt = (time.perf_counter() - t0) * 1000
                if cur.description:
                    cols = [d.name for d in cur.description]
                    rows = cur.fetchall()
                    if cols == ["QUERY PLAN"]:
                        for (r,) in rows:
                            emit(r)
                    else:
                        emit(" | ".join(cols))
                        for r in rows:
                            emit(" | ".join("" if v is None else str(v) for v in r))
                        emit(f"({len(rows)} rows, {dt:.1f} ms wall)")
                else:
                    emit(f"OK ({cur.statusmessage}, {dt:.1f} ms wall)")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nsaved -> {out_path.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main(sys.argv[1])
