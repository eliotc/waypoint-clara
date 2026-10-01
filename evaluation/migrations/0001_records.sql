-- Evaluation outcome records: immutable audit and review store.
-- Apply to the waypoint database under SCHEMA evaluation. It creates the evaluation schema,
-- core tables, foreign keys, query indexes, and three NOLOGIN group roles:
--
--   * waypoint_eval_record_writer: SELECT and INSERT on evaluation schema tables only.
--     Strictly NO UPDATE or DELETE grants. No write access to application tables.
--   * waypoint_eval_record_reader: SELECT on all evaluation tables, views, and sequences.
--     Used for internal triage and complete behind-the-scenes audit history.
--   * waypoint_eval_public_reader: SELECT on evaluation.public_assessment_summaries ONLY.
--     Cannot access raw dialogue traces, evidence excerpts, or JSON payloads.
--
-- No grants are made to PUBLIC.
BEGIN;
CREATE SCHEMA IF NOT EXISTS evaluation;
REVOKE ALL ON SCHEMA evaluation FROM PUBLIC;

CREATE TABLE IF NOT EXISTS evaluation.eval_runs (
    run_id text PRIMARY KEY,
    started_at timestamptz NOT NULL,
    status text NOT NULL,
    agent_name text NOT NULL,
    model_id text NOT NULL,
    scenario_id text,
    git_commit text,
    git_dirty boolean,
    dataset_version text,
    payload jsonb NOT NULL CHECK (payload->>'record_type' = 'run')
);

CREATE TABLE IF NOT EXISTS evaluation.eval_assessments (
    assessment_id text PRIMARY KEY,
    run_id text NOT NULL REFERENCES evaluation.eval_runs(run_id),
    assessed_at timestamptz NOT NULL,
    evaluator_kind text NOT NULL,
    reviewer_role text NOT NULL,
    evaluator_model_id text,
    rubric_version text NOT NULL,
    supersedes_assessment_id text REFERENCES evaluation.eval_assessments(assessment_id),
    total_opportunities integer NOT NULL CHECK (total_opportunities >= 0),
    passes integer NOT NULL CHECK (passes >= 0),
    issues integer NOT NULL CHECK (issues >= 0),
    incomplete integer NOT NULL CHECK (incomplete >= 0),
    execution_errors integer NOT NULL CHECK (execution_errors >= 0),
    payload jsonb NOT NULL CHECK (payload->>'record_type' = 'assessment'),
    CHECK (total_opportunities = passes + issues + incomplete + execution_errors)
);

CREATE TABLE IF NOT EXISTS evaluation.eval_issues (
    issue_id text PRIMARY KEY,
    title text NOT NULL,
    status text NOT NULL,
    primary_layer text NOT NULL,
    first_observed_run_id text REFERENCES evaluation.eval_runs(run_id),
    first_observed_assessment_id text REFERENCES evaluation.eval_assessments(assessment_id),
    payload jsonb NOT NULL CHECK (payload->>'record_type' = 'issue')
);

CREATE TABLE IF NOT EXISTS evaluation.eval_results (
    assessment_id text NOT NULL REFERENCES evaluation.eval_assessments(assessment_id),
    result_id text NOT NULL,
    criterion_id text NOT NULL,
    outcome text NOT NULL,
    severity text,
    tags text[] NOT NULL DEFAULT '{}',
    issue_id text REFERENCES evaluation.eval_issues(issue_id),
    payload jsonb NOT NULL,
    PRIMARY KEY (assessment_id, result_id)
);

CREATE TABLE IF NOT EXISTS evaluation.eval_verification_events (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    occurred_at timestamptz NOT NULL,
    target_issue_id text REFERENCES evaluation.eval_issues(issue_id),
    verification_run_id text REFERENCES evaluation.eval_runs(run_id),
    verification_assessment_id text REFERENCES evaluation.eval_assessments(assessment_id),
    payload jsonb NOT NULL CHECK (payload->>'record_type' = 'verification_event')
);

CREATE INDEX IF NOT EXISTS eval_runs_model_started_idx ON evaluation.eval_runs(model_id, started_at DESC);
CREATE INDEX IF NOT EXISTS eval_assessments_run_idx ON evaluation.eval_assessments(run_id, assessed_at DESC);
CREATE INDEX IF NOT EXISTS eval_results_criterion_outcome_idx ON evaluation.eval_results(criterion_id, outcome);
CREATE INDEX IF NOT EXISTS eval_results_tags_idx ON evaluation.eval_results USING gin(tags);
CREATE INDEX IF NOT EXISTS eval_issues_layer_status_idx ON evaluation.eval_issues(primary_layer, status);
CREATE INDEX IF NOT EXISTS eval_events_issue_time_idx ON evaluation.eval_verification_events(target_issue_id, occurred_at DESC);

-- Use this for current-outcome trends; historical assessments remain queryable.
-- Detailed view including JSONB payloads; for internal evaluation readers/writers.
CREATE OR REPLACE VIEW evaluation.current_assessments AS
SELECT a.* FROM evaluation.eval_assessments a
WHERE NOT EXISTS (
    SELECT 1 FROM evaluation.eval_assessments successor
    WHERE successor.supersedes_assessment_id = a.assessment_id
);

-- Deliberately limited summary view; safe for public or general application readers.
-- Excludes all raw payloads, transcripts, and evidence excerpts.
CREATE OR REPLACE VIEW evaluation.public_assessment_summaries AS
SELECT 
    a.assessment_id,
    a.run_id,
    a.assessed_at,
    a.evaluator_kind,
    a.reviewer_role,
    a.evaluator_model_id,
    a.rubric_version,
    a.total_opportunities,
    a.passes,
    a.issues,
    a.incomplete,
    a.execution_errors,
    r.agent_name,
    r.model_id AS run_model_id,
    r.scenario_id,
    r.started_at AS run_started_at,
    r.status AS run_status
FROM evaluation.current_assessments a
JOIN evaluation.eval_runs r ON a.run_id = r.run_id;

-- Group roles have no login. Create login roles separately and grant membership.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'waypoint_eval_record_writer') THEN
        CREATE ROLE waypoint_eval_record_writer NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'waypoint_eval_record_reader') THEN
        CREATE ROLE waypoint_eval_record_reader NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'waypoint_eval_public_reader') THEN
        CREATE ROLE waypoint_eval_public_reader NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA evaluation TO waypoint_eval_record_writer, waypoint_eval_record_reader, waypoint_eval_public_reader;

-- Writer: can insert records and read evaluation schema; strictly cannot update or delete
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA evaluation TO waypoint_eval_record_writer;
GRANT SELECT ON evaluation.current_assessments TO waypoint_eval_record_writer;
GRANT SELECT ON evaluation.public_assessment_summaries TO waypoint_eval_record_writer;

-- Detailed Reader: can read all tables and complete assessment views (including JSONB)
GRANT SELECT ON ALL TABLES IN SCHEMA evaluation TO waypoint_eval_record_reader;
GRANT SELECT ON evaluation.current_assessments TO waypoint_eval_record_reader;
GRANT SELECT ON evaluation.public_assessment_summaries TO waypoint_eval_record_reader;

-- Public Reader: can ONLY read the sanitized summary view
GRANT SELECT ON evaluation.public_assessment_summaries TO waypoint_eval_public_reader;

COMMIT;
