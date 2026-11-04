-- Claiming: let an owner ask for a found item, and let the finder approve or decline.
-- Also records when something was lost/found and where a found item is right now.

ALTER TABLE item
    ADD COLUMN happened_on     date NOT NULL DEFAULT CURRENT_DATE,  -- when it was lost/found
    ADD COLUMN held_at         varchar(100),                        -- found items: where it is now
    ADD COLUMN verify_question varchar(200);                        -- found items: asked of claimants

CREATE TABLE claims (
    claim_id    serial      PRIMARY KEY,
    item_id     integer     NOT NULL REFERENCES item (item_id) ON DELETE CASCADE,
    claimant_id integer     NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    answer      varchar(500) NOT NULL,
    status      varchar(10) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'approved', 'declined')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    decided_at  timestamptz,
    UNIQUE (item_id, claimant_id)
);

CREATE INDEX claims_item_idx ON claims (item_id);
CREATE INDEX claims_claimant_idx ON claims (claimant_id);
