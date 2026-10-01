CREATE TABLE IF NOT EXISTS fix_step (
    borrower_id  VARCHAR(20)  NOT NULL,
    mechanism    VARCHAR(40)  NOT NULL,
    code         VARCHAR(60)  NOT NULL,
    title        VARCHAR(200) NOT NULL,
    kind         VARCHAR(10)  NOT NULL,
    status       VARCHAR(20)  NOT NULL,
    draft        CLOB,
    draft_source VARCHAR(30),
    owner        VARCHAR(80),
    due_date     DATE,
    decided_by   VARCHAR(80),
    decided_at   TIMESTAMP,
    note         VARCHAR(1000),
    created_at   TIMESTAMP    NOT NULL,
    clues        VARCHAR(4000),  -- for a "worth a look" check: the clues it asked about, one per line
    PRIMARY KEY (borrower_id, mechanism, code)
);
-- databases created before clue tracking (1 Oct 2026)
ALTER TABLE fix_step ADD COLUMN IF NOT EXISTS clues VARCHAR(4000);

CREATE TABLE IF NOT EXISTS audit_event (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    at          TIMESTAMP     NOT NULL,
    actor       VARCHAR(80)   NOT NULL,
    borrower_id VARCHAR(20),
    action      VARCHAR(40)   NOT NULL,
    detail      VARCHAR(2000)
);
