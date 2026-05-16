BEGIN;

ALTER TABLE instagram_conversation_state
  ADD COLUMN IF NOT EXISTS campaign_id TEXT,
  ADD COLUMN IF NOT EXISTS ad_id TEXT,
  ADD COLUMN IF NOT EXISTS product_tag TEXT;

COMMENT ON COLUMN instagram_conversation_state.campaign_id IS 'Instagram referral/mid from ad campaign';
COMMENT ON COLUMN instagram_conversation_state.ad_id IS 'Instagram ad_id from referral metadata';
COMMENT ON COLUMN instagram_conversation_state.product_tag IS 'Product name from campaign referral (message.referral.product_name)';

COMMIT;
