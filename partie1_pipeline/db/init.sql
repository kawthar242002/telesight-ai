-- TeleSight AI — PostgreSQL Schema
-- Run automatically on first start via Docker Compose volume mount

CREATE TABLE IF NOT EXISTS kpi_records (
    id               BIGSERIAL PRIMARY KEY,
    cell_id          VARCHAR(32)   NOT NULL,
    timestamp        TIMESTAMPTZ   NOT NULL,
    technology       VARCHAR(8)    NOT NULL DEFAULT '5G',
    rsrp             FLOAT,
    rsrq             FLOAT,
    sinr             FLOAT,
    throughput_dl    FLOAT,
    throughput_ul    FLOAT,
    latency          FLOAT,
    jitter           FLOAT,
    packet_loss      FLOAT,
    handover_label   SMALLINT      DEFAULT 0,
    is_anomaly       SMALLINT      DEFAULT 0,
    latitude         FLOAT,
    longitude        FLOAT,
    signal_score     FLOAT,
    qos_score        FLOAT,
    alert_level      VARCHAR(16)   DEFAULT 'normal',
    spectral_efficiency FLOAT,
    prb_utilization  FLOAT,
    active_users     INT,
    created_at       TIMESTAMPTZ   DEFAULT NOW()
);

-- Index for fast queries by cell + time
CREATE INDEX IF NOT EXISTS idx_kpi_cell_time  ON kpi_records (cell_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_kpi_alert      ON kpi_records (alert_level);
CREATE INDEX IF NOT EXISTS idx_kpi_anomaly    ON kpi_records (is_anomaly);
CREATE INDEX IF NOT EXISTS idx_kpi_timestamp  ON kpi_records (timestamp DESC);

-- Latest KPI per cell (materialized view for fast reads)
CREATE TABLE IF NOT EXISTS cell_latest (
    cell_id         VARCHAR(32)   PRIMARY KEY,
    technology      VARCHAR(8),
    rsrp            FLOAT,
    rsrq            FLOAT,
    sinr            FLOAT,
    throughput_dl   FLOAT,
    throughput_ul   FLOAT,
    latency         FLOAT,
    jitter          FLOAT,
    packet_loss     FLOAT,
    handover_label  SMALLINT,
    is_anomaly      SMALLINT,
    latitude        FLOAT,
    longitude       FLOAT,
    signal_score    FLOAT,
    qos_score       FLOAT,
    alert_level     VARCHAR(16),
    spectral_efficiency FLOAT,
    prb_utilization FLOAT,
    active_users    INT,
    last_updated    TIMESTAMPTZ   DEFAULT NOW()
);

-- Anomaly events log
CREATE TABLE IF NOT EXISTS anomaly_events (
    id          BIGSERIAL PRIMARY KEY,
    cell_id     VARCHAR(32)  NOT NULL,
    timestamp   TIMESTAMPTZ  NOT NULL,
    alert_level VARCHAR(16),
    sinr        FLOAT,
    latency     FLOAT,
    throughput_dl FLOAT,
    anomaly_score FLOAT,
    explanation TEXT,
    resolved    BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomaly_cell ON anomaly_events (cell_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_resolved ON anomaly_events (resolved, created_at DESC);
