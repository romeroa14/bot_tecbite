-- Persist roof type in Instagram conversation state for kit 5/6/7 search flow
BEGIN;

ALTER TABLE instagram_conversation_state
  ADD COLUMN IF NOT EXISTS roof_type TEXT;

-- Extend allowed stages (idempotent: drop/recreate if exists)
ALTER TABLE instagram_conversation_state
  DROP CONSTRAINT IF EXISTS instagram_conversation_state_stage_chk;

ALTER TABLE instagram_conversation_state
  ADD CONSTRAINT instagram_conversation_state_stage_chk CHECK (
    stage IN (
      'ask_make', 'ask_model', 'ask_year', 'ask_roof', 'ask_category',
      'collect_make', 'collect_model', 'collect_year', 'collect_roof', 'collect_category',
      'recommend', 'handoff', 'greeting'
    )
  );

CREATE INDEX IF NOT EXISTS idx_instagram_state_roof_lookup
  ON instagram_conversation_state (
    LOWER(COALESCE(make, '')),
    LOWER(COALESCE(model, '')),
    year,
    COALESCE(roof_type, '')
  );

COMMIT;
