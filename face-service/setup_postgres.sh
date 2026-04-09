#!/usr/bin/env bash
# =============================================================================
# setup_postgres.sh — SmartAttend pgvector database setup
#
# Run this ONCE on a machine where PostgreSQL is installed.
# Then set DB_ENABLED=true and DB_DSN in your face-service environment.
#
# Prerequisites:
#   sudo apt-get install -y postgresql postgresql-contrib
#   sudo apt-get install -y postgresql-<ver>-pgvector   # or build from source
#
# Usage:
#   bash setup_postgres.sh
#   bash setup_postgres.sh --drop     # drop + recreate (destructive!)
# =============================================================================
set -euo pipefail

DB_USER="smartattend"
DB_PASS="smartattend"
DB_NAME="smartattend_faces"
PG_HOST="localhost"
PG_PORT="5432"

DROP=false
for arg in "$@"; do
    [ "$arg" = "--drop" ] && DROP=true
done

echo "=== SmartAttend — PostgreSQL + pgvector setup ==="
echo "  DB user : $DB_USER"
echo "  DB name : $DB_NAME"
echo "  Host    : $PG_HOST:$PG_PORT"
echo ""

# ── Create role if it doesn't exist ──────────────────────────────────────────
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" \
    | grep -q 1 \
    || sudo -u postgres psql -c "CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASS';"
echo "[OK] Role $DB_USER"

# ── Drop database (only with --drop) ─────────────────────────────────────────
if [ "$DROP" = true ]; then
    echo "[WARN] Dropping database $DB_NAME …"
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS $DB_NAME;"
fi

# ── Create database if it doesn't exist ──────────────────────────────────────
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" \
    | grep -q 1 \
    || sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
echo "[OK] Database $DB_NAME"

# ── Apply schema ──────────────────────────────────────────────────────────────
sudo -u postgres psql -d "$DB_NAME" <<'SQL'
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Main embeddings table
CREATE TABLE IF NOT EXISTS student_face_embeddings (
    id          SERIAL PRIMARY KEY,
    roll_number TEXT        NOT NULL,
    embedding   vector(512) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    is_active   BOOLEAN     DEFAULT TRUE,
    source      TEXT        DEFAULT 'insightface_buffalo_l'
);

-- Fast lookup by roll number
CREATE INDEX IF NOT EXISTS idx_face_emb_roll
    ON student_face_embeddings (roll_number);

-- HNSW index for approximate nearest-neighbour search (cosine)
-- Used by find_top_k_similar() (debug only, not in attendance path)
CREATE INDEX IF NOT EXISTS idx_face_emb_hnsw
    ON student_face_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH  (m = 16, ef_construction = 64);

SQL

echo "[OK] Schema applied (table + indexes)"

# ── Grant privileges ──────────────────────────────────────────────────────────
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO $DB_USER;"
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;"
echo "[OK] Privileges granted to $DB_USER"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Add these to your face-service environment (or .env file):"
echo "  DB_ENABLED=true"
echo "  DB_DSN=postgresql://$DB_USER:$DB_PASS@$PG_HOST:$PG_PORT/$DB_NAME"
echo ""
echo "Then run the migration:"
echo "  cd face-service"
echo "  ./venv/bin/python3 migrate_embeddings.py"