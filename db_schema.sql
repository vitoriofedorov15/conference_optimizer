-- Новая таблица: серии конференций
CREATE TABLE conference_series (
    id           SERIAL PRIMARY KEY,
    series_key   TEXT NOT NULL,
    key_type     VARCHAR(10) NOT NULL DEFAULT 'name'
                 CHECK (key_type IN ('abbr', 'title', 'name')),
    display_name TEXT,
    confidence   VARCHAR(10) DEFAULT 'high'
                 CHECK (confidence IN ('high', 'medium', 'low')),
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_series_key_type ON conference_series (series_key, key_type);
CREATE INDEX idx_series_key ON conference_series (series_key);


-- Изменения в существующей таблице conferences
ALTER TABLE conferences ADD COLUMN IF NOT EXISTS series_id   INTEGER REFERENCES conference_series(id) ON DELETE SET NULL;
ALTER TABLE conferences ADD COLUMN IF NOT EXISTS year        INTEGER CHECK (year IS NULL OR (year >= 1900 AND year <= 2099));
ALTER TABLE conferences ADD COLUMN IF NOT EXISTS location    TEXT;
ALTER TABLE conferences ADD COLUMN IF NOT EXISTS series_key  TEXT;
ALTER TABLE conferences ADD COLUMN IF NOT EXISTS key_type    VARCHAR(10) CHECK (key_type IS NULL OR key_type IN ('abbr', 'title', 'name'));
ALTER TABLE conferences ADD COLUMN IF NOT EXISTS parent_conference_id INTEGER REFERENCES conferences(id) ON DELETE SET NULL;
ALTER TABLE conferences ADD COLUMN IF NOT EXISTS is_container BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_conferences_series_id ON conferences (series_id);
CREATE INDEX IF NOT EXISTS idx_conferences_year      ON conferences (year);
CREATE INDEX IF NOT EXISTS idx_conferences_parent    ON conferences (parent_conference_id);
CREATE INDEX IF NOT EXISTS idx_conferences_series_key ON conferences (series_key);


-- VIEW: дерево серия → выпуск → дочерние
CREATE OR REPLACE VIEW v_conference_tree AS
SELECT
    cs.series_key,
    cs.confidence,
    parent.id           AS edition_id,
    parent.full_name    AS edition_name,
    parent.year         AS edition_year,
    parent.location     AS edition_location,
    child.id            AS child_id,
    child.full_name     AS child_name,
    child.isand_id      AS child_isand_id
FROM conference_series cs
JOIN conferences parent ON parent.series_id = cs.id AND parent.is_container = TRUE
LEFT JOIN conferences child ON child.parent_conference_id = parent.id
ORDER BY cs.series_key, parent.year NULLS LAST;


-- VIEW: статистика по сериям
CREATE OR REPLACE VIEW v_series_stats AS
SELECT
    cs.id, cs.series_key, cs.display_name, cs.key_type, cs.confidence,
    COUNT(c.id)                                   AS total_editions,
    MIN(c.year)                                   AS first_year,
    MAX(c.year)                                   AS last_year,
    STRING_AGG(DISTINCT c.location, ', ' ORDER BY c.location) AS locations
FROM conference_series cs
LEFT JOIN conferences c ON c.series_id = cs.id
GROUP BY cs.id, cs.series_key, cs.display_name, cs.key_type, cs.confidence
ORDER BY total_editions DESC;
