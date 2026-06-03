# Database package

## Seed size (current)

| | |
|--|--|
| **Artifacts** | **None** — `seed.sql` is profiles-only |
| **Demo data** | Removed; use `purge_demo_seed.sql` on old DBs |
| **Profiles** | 2 (`buildradar`, `vibecoder`) |

All searchable artifacts come from **crawlers** (HN / GitHub / arXiv).

## Fat seed + live updates (recommended)

1. Run crawlers until happy (e.g. `docker compose up -d` with the `crawler` service, or `workers/bootstrap_index.py`).
2. Export the live index into seed:

```bash
pip install asyncpg   # if needed
python packages/db/export_seed_from_db.py --limit 300 --min-quality 55
```

3. Commit `packages/db/seed.sql`.

**New users** on first `docker compose up` get hundreds of artifacts immediately. The **crawler** keeps refreshing after that.

### Important: seed only runs on a **new** Postgres volume

Existing Docker volumes already ran init scripts. To apply a new seed locally:

```bash
docker compose down -v   # wipes DB volume — destructive
docker compose up -d
```

Or apply without wiping:

```bash
docker exec -i build_radar_pg psql -U postgres -d build_radar < packages/db/seed.sql
```

(`on conflict (canonical_url) do nothing` skips duplicates.)

## Files

- `schema.sql` — tables, indexes, triggers
- `seed.sql` — starter (or exported) data
- `export_seed_from_db.py` — build seed from crawled DB
