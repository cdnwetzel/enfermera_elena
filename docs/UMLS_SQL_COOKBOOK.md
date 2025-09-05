# UMLS Mapping – Full vs Subset & SQL Cookbook

This markdown is a pragmatic guide to choose between UMLS packages and to extract a Spanish→English medical glossary for our on‑prem pipeline.

---

## Which package should we use?

### TL;DR

* **Production / maximum power**: **Full Release (RRF files)** → load `MRCONSO.RRF` (+ optional `MRREL.RRF`, `MRSTY.RRF`) into a DB. You control everything (languages, vocab priorities, dedup, coverage).
* **Faster start with nearly full coverage**: **Metathesaurus Full Subset** → precomputed, easier to ingest; still large; sometimes opinionated column choices.
* **Prototype only**: **Level 0 Subset** → small, simplified; fine to validate wiring, **not** enough coverage for Mexican clinical text.

### Decision matrix

| Need                                               | Full Release (RRF) | Full Subset             | Level 0 Subset |
| -------------------------------------------------- | ------------------ | ----------------------- | -------------- |
| Max vocab coverage (SNOMED/ICD/RxNorm/LOINC, etc.) | ★★★★★              | ★★★★☆                   | ★★☆☆☆          |
| Spanish variants (incl. Mexico)                    | ★★★★★              | ★★★★☆                   | ★★☆☆☆          |
| Control over dedup & priority rules                | ★★★★★              | ★★★☆☆                   | ★★☆☆☆          |
| Ease of ingestion                                  | ★★☆☆☆              | ★★★★☆                   | ★★★★★          |
| Prototype speed                                    | ★★☆☆☆              | ★★★★☆                   | ★★★★★          |
| Best choice for us                                 | **✔**              | ✔ (if time‑constrained) | Prototype only |

**Recommendation:** use **Full Release** for the long‑term build. If you want to stand up a proof quickly, first run on the **Full Subset**, keeping the SQL below (it works on either once columns are mapped).

---

## Install & load (SQLite or Postgres)

### 1) Use MetamorphoSys (optional but helpful)

* Install the Full Release.
* Create a custom subset with: `LAT ∈ {SPA, ENG}`, preferred terms only (TTY=PT) **plus** synonyms (TTY=SY) if you want broader matching.
* Output: slimmer `.RRF` files → faster load.

### 2) Minimal schemas

**SQLite** (quick local dev):

```sql
-- MRCONSO minimal projection (add columns as needed)
CREATE TABLE mrconso (
  CUI TEXT,
  LAT TEXT,
  TS  TEXT,
  LUI TEXT,
  STT TEXT,
  SUI TEXT,
  ISPREF TEXT,
  AUI TEXT,
  SAUI TEXT,
  SCUI TEXT,
  SDUI TEXT,
  SAB TEXT,
  TTY TEXT,
  CODE TEXT,
  STR TEXT,
  SRL TEXT,
  SUPPRESS TEXT,
  CVF TEXT
);
CREATE INDEX idx_conso_cui ON mrconso(CUI);
CREATE INDEX idx_conso_lang ON mrconso(LAT);
CREATE INDEX idx_conso_tty ON mrconso(TTY);
CREATE INDEX idx_conso_str ON mrconso(STR);
```

**Postgres** (preferred for scale):

```sql
CREATE TABLE mrconso (
  CUI TEXT,
  LAT TEXT,
  TS  TEXT,
  LUI TEXT,
  STT TEXT,
  SUI TEXT,
  ISPREF TEXT,
  AUI TEXT,
  SAUI TEXT,
  SCUI TEXT,
  SDUI TEXT,
  SAB TEXT,
  TTY TEXT,
  CODE TEXT,
  STR TEXT,
  SRL TEXT,
  SUPPRESS TEXT,
  CVF TEXT
);
CREATE INDEX ON mrconso(CUI);
CREATE INDEX ON mrconso(LAT);
CREATE INDEX ON mrconso(TTY);
-- Optional full‑text index for STR if you plan fuzzy matching later
```

### 3) Import MRCONSO.RRF

* It's `|` (pipe) delimited, **with** escaped pipes rare but possible; fields are fixed in order.
* SQLite: use `.mode ascii` + `.separator "|"` in `sqlite3`, or import via Python/psql scripts.
* Postgres: use `COPY mrconso FROM '/path/MRCONSO.RRF' WITH (FORMAT csv, DELIMITER '|', QUOTE '"', ESCAPE '"');`

---

## Core SQL: Spanish→English preferred mapping

**Goal:** build a two‑column glossary `es_term → en_pref` anchored by CUI, prioritizing SNOMED CT (Mexico) where available.

```sql
-- 1) Preferred English term per CUI (PT)
WITH en_pref AS (
  SELECT CUI, STR AS en_term,
         ROW_NUMBER() OVER (
           PARTITION BY CUI ORDER BY
             CASE WHEN SAB LIKE 'SNOMED%' THEN 0 ELSE 1 END,
             CASE WHEN ISPREF='Y' THEN 0 ELSE 1 END
         ) AS rk
  FROM mrconso
  WHERE LAT='ENG' AND TTY='PT'
),
-- 2) Spanish surface forms to map (PT first, then SY fallback)
es_src AS (
  SELECT CUI, STR AS es_term, 0 AS pref_rank
  FROM mrconso WHERE LAT='SPA' AND TTY='PT'
  UNION ALL
  SELECT CUI, STR AS es_term, 1 AS pref_rank
  FROM mrconso WHERE LAT='SPA' AND TTY='SY'
),
-- 3) pick a single English preferred per CUI
best_en AS (
  SELECT CUI, en_term FROM en_pref WHERE rk=1
)
SELECT DISTINCT es.es_term, be.en_term, es.CUI
FROM es_src es
JOIN best_en be USING (CUI)
WHERE es.es_term IS NOT NULL AND be.en_term IS NOT NULL;
```

### Variant: prefer SNOMED CT Mexico explicitly for Spanish

```sql
WITH es_src AS (
  SELECT CUI, STR AS es_term, 0 AS pref_rank
  FROM mrconso WHERE LAT='SPA' AND SAB IN ('SNOMEDCT', 'SNOMEDCT_MX') AND TTY IN ('PT','SY')
  UNION ALL
  SELECT CUI, STR AS es_term, 1 AS pref_rank
  FROM mrconso WHERE LAT='SPA' AND TTY IN ('PT','SY')
),
be AS (
  SELECT CUI, STR AS en_term,
         ROW_NUMBER() OVER (PARTITION BY CUI ORDER BY CASE WHEN SAB LIKE 'SNOMED%' THEN 0 ELSE 1 END) rk
  FROM mrconso WHERE LAT='ENG' AND TTY='PT'
)
SELECT DISTINCT es.es_term, be.en_term, es.CUI
FROM es_src es JOIN be ON es.CUI=be.CUI AND be.rk=1;
```

### Dedup & normalization (recommended)

```sql
-- Normalize casing/whitespace and dedup
CREATE TABLE glossary_es_en AS
SELECT DISTINCT
  TRIM(LOWER(es_term)) AS es_norm,
  TRIM(be.en_term)     AS en_term,
  CUI
FROM (
  -- (use one of the SELECTs above)
) t;

-- Optional: collapse many‑to‑one Spanish terms by frequency or SNOMED priority
```

Export this as CSV for the pipeline glossary (source→target). Keep CUIs for audit.

---

## Performance tips

* Index `mrconso(LAT, TTY, SAB)` before running the CTEs.
* If memory is tight, materialize `en_pref`, `es_src` as temp tables.
* Consider a tiny auxiliary table listing **allowed SABs** (SNOMED, ICD10, etc.) to filter early.

---

## Prototype path with Level 0 Subset

* Yes, **Level 0** can drive a quick prototype. Run the same SQL (column names match MRCONSO). Expect lower hit‑rates on Mexican terms.
* Use it to verify the *wiring* (De‑ID → Mapping → MT glossary). Then switch to **Full Subset** or **Full Release** for real coverage.

---

## Next steps

1. Load MRCONSO into Postgres (recommended) using the schema above.
2. Run the "Core SQL" to generate `glossary_es_en.csv` (two columns: `es_term,en_term`).
3. Plug the CSV into the pipeline's MT glossary input; keep `__PHI_*__` in the engine's do‑not‑translate list.
4. Iterate vocab priority rules (prefer SNOMED MX, then UMLS ES, then ICD‑10 ES) based on QA.