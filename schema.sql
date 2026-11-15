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

-- Intentionally incomplete baseline: election does not enforce write ownership.
CREATE FUNCTION store_result(p_epoch bigint, p_job_id text, p_value text)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO scheduler_result (job_id, epoch, value)
    VALUES (p_job_id, p_epoch, p_value)
    ON CONFLICT (job_id) DO UPDATE
       SET epoch = EXCLUDED.epoch, value = EXCLUDED.value;
END;
$$;
