CREATE TABLE scheduler_leader (
    name text PRIMARY KEY,
    epoch bigint NOT NULL CHECK (epoch >= 0)
);

INSERT INTO scheduler_leader (name, epoch) VALUES ('scheduler', 0);

CREATE TABLE scheduler_result (
    job_id text PRIMARY KEY,
    epoch bigint NOT NULL,
    value text NOT NULL
);

-- Serialize write authorization with the committed leader-epoch transition.
CREATE FUNCTION store_result(p_epoch bigint, p_job_id text, p_value text)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    current_epoch bigint;
BEGIN
    SELECT epoch INTO current_epoch
      FROM scheduler_leader
     WHERE name = 'scheduler'
       FOR UPDATE;

    IF NOT FOUND OR current_epoch IS DISTINCT FROM p_epoch THEN
        RAISE EXCEPTION 'stale or missing scheduler epoch'
            USING ERRCODE = 'P0001';
    END IF;

    INSERT INTO scheduler_result (job_id, epoch, value)
    VALUES (p_job_id, p_epoch, p_value)
    ON CONFLICT (job_id) DO UPDATE
       SET epoch = EXCLUDED.epoch, value = EXCLUDED.value;
END;
$$;
