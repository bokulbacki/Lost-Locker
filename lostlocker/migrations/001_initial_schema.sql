-- Initial schema for Lost Locker.
--
-- Model: an item has one item type (Clothing, Bottle, ...). Each item type allows a set of
-- attribute values (brand, colour, ...) listed in item_attribute. An item's chosen values are
-- stored in item_detail. Matching a lost item to a found item compares those values.

CREATE TABLE users (
    user_id       serial PRIMARY KEY,
    email         varchar(254) NOT NULL UNIQUE CHECK (email = lower(email)),
    name          varchar(100) NOT NULL,
    password_hash varchar(255) NOT NULL,
    is_admin      boolean      NOT NULL DEFAULT false,
    created_at    timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE itemtype (
    itemtype_id    integer     PRIMARY KEY,
    itemtype       varchar(40) NOT NULL UNIQUE,
    -- true when the reporter must type a title (e.g. the name of a book)
    requires_title boolean     NOT NULL DEFAULT false
);

CREATE TABLE attributetype (
    attributetype_id integer      PRIMARY KEY,
    attributetype    varchar(100) NOT NULL,  -- the group, e.g. 'Brand'
    description      varchar(100) NOT NULL,  -- the value, e.g. 'Nike'
    UNIQUE (attributetype, description)
);

-- Which attribute values may be chosen for which item type.
CREATE TABLE item_attribute (
    itemtype_id      integer NOT NULL REFERENCES itemtype (itemtype_id),
    attributetype_id integer NOT NULL REFERENCES attributetype (attributetype_id),
    PRIMARY KEY (itemtype_id, attributetype_id)
);

CREATE TABLE item (
    item_id           serial       PRIMARY KEY,
    itemtype_id       integer      NOT NULL REFERENCES itemtype (itemtype_id),
    status            varchar(20)  NOT NULL CHECK (status IN ('Lost', 'Found', 'Returned')),
    -- the status an item had before it was marked Returned, so we know what it was
    reported_as       varchar(20)  NOT NULL CHECK (reported_as IN ('Lost', 'Found')),
    book_title        varchar(200),
    notes             varchar(500),
    image_filename    varchar(64),
    submitted_by_user integer      NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    date_reported     date         NOT NULL DEFAULT CURRENT_DATE,
    created_at        timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX item_status_idx ON item (status, itemtype_id);
CREATE INDEX item_user_idx   ON item (submitted_by_user);

CREATE TABLE item_detail (
    item_id          integer NOT NULL REFERENCES item (item_id) ON DELETE CASCADE,
    attributetype_id integer NOT NULL REFERENCES attributetype (attributetype_id),
    PRIMARY KEY (item_id, attributetype_id)
);

CREATE INDEX item_detail_attr_idx ON item_detail (attributetype_id);

-- A possible pairing of a lost report with a found report.
CREATE TABLE matches (
    match_id      serial       PRIMARY KEY,
    lost_item_id  integer      NOT NULL REFERENCES item (item_id) ON DELETE CASCADE,
    found_item_id integer      NOT NULL REFERENCES item (item_id) ON DELETE CASCADE,
    score         numeric(5,2) NOT NULL,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    notified_at   timestamptz,  -- when the owner was emailed (null: not emailed)
    UNIQUE (lost_item_id, found_item_id)
);

CREATE INDEX matches_found_idx ON matches (found_item_id);

-- Found items that are still waiting to be claimed, one row per chosen attribute.
CREATE VIEW locker_items AS
SELECT i.item_id,
       i.status,
       it.itemtype,
       a.attributetype,
       a.description
FROM item i
JOIN itemtype it     ON it.itemtype_id = i.itemtype_id
LEFT JOIN item_detail d ON d.item_id = i.item_id
LEFT JOIN attributetype a ON a.attributetype_id = d.attributetype_id
WHERE i.status = 'Found';
