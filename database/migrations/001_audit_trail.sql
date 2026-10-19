-- Brings an existing database's AUDIT table in line with schema.sql.
-- Safe to run once on a database created from the old schema.

BEGIN;

-- Record the time of day, not just the date. Existing rows keep their
-- date, at midnight.
ALTER TABLE public."AUDIT"
    ALTER COLUMN time_stamp TYPE timestamp with time zone USING time_stamp::timestamp with time zone;
UPDATE public."AUDIT" SET time_stamp = now() WHERE time_stamp IS NULL;
ALTER TABLE public."AUDIT"
    ALTER COLUMN time_stamp SET DEFAULT now(),
    ALTER COLUMN time_stamp SET NOT NULL;

-- Deleting a user must not be blocked by their audit history. The entry
-- text still names the actor by email.
ALTER TABLE public."AUDIT" DROP CONSTRAINT IF EXISTS forein_key_user_id;
ALTER TABLE public."AUDIT"
    ADD CONSTRAINT forein_key_user_id FOREIGN KEY (user_id)
    REFERENCES public."USER" (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_audit_time_stamp ON public."AUDIT" (time_stamp DESC);

COMMIT;
