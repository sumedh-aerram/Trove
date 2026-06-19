-- Trove seed data (profiles only — no fake demo artifacts).
-- Artifacts come from crawlers (HN, GitHub, arXiv) or export_seed_from_db.py.
-- search_vector / embeddings are filled at ingest or via backfill_embeddings.py.

insert into profiles (username, display_name, bio, github_url, website_url, credibility_score)
values
  ('buildradar', 'Trove', 'Official account.', null, null, 50),
  ('vibecoder', 'Vibe Coder', 'Ships weekend AI apps.', null, null, 20)
on conflict (username) do nothing;
