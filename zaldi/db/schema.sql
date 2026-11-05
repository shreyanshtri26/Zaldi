CREATE TABLE IF NOT EXISTS products (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code   TEXT NOT NULL UNIQUE,
    product_name   TEXT NOT NULL,
    category       TEXT,
    material       TEXT,
    size           TEXT,
    color          TEXT,
    brand          TEXT,
    gender         TEXT,
    stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    price          INTEGER NOT NULL CHECK (price >= 0),   -- INR, GST inclusive
    description    TEXT,
    image_url      TEXT,
    updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policies (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL UNIQUE,
    content    TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    query      TEXT NOT NULL,
    response   TEXT,
    route      TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Overrides only: a missing row means "use the built-in default".
CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prompts (
    name       TEXT PRIMARY KEY,
    content    TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Suggestion cards on the chat welcome screen.
CREATE TABLE IF NOT EXISTS quick_actions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    subtitle   TEXT,
    message    TEXT NOT NULL,                       -- sent to the assistant when the card is clicked
    icon       TEXT NOT NULL DEFAULT 'chat',
    position   INTEGER NOT NULL DEFAULT 0,
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---- Shopping sessions (anonymous: the browser keeps a random session id) ----
CREATE TABLE IF NOT EXISTS preferences (
    session_id     TEXT PRIMARY KEY,
    max_price      INTEGER CHECK (max_price IS NULL OR max_price >= 0),
    brand          TEXT,                 -- only show this brand
    exclude_brands TEXT,                 -- comma-separated brands never to show
    size           TEXT,
    gender         TEXT,
    updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session_state (
    session_id   TEXT PRIMARY KEY,
    last_results TEXT NOT NULL DEFAULT '[]',   -- product ids last shown, so "add the first one" has a referent
    coupon       TEXT,
    updated_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cart_items (
    session_id TEXT NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (session_id, product_id)
);

-- One row per checkout the automation prepared; confirmed at most once, only by the customer.
CREATE TABLE IF NOT EXISTS orders (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    summary      TEXT NOT NULL,         -- JSON: items, totals, masked address
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TEXT
);
