#!/usr/bin/env bash
# =============================================================================
# Limpia el hilo de conversación de Instagram en Postgres.
#
# Borra estado y eventos de instagram_conversation_state / instagram_conversation_event
# para un conversation_id dado (por defecto: tu usuario real de pruebas).
#
# Uso:
#   ./scripts/ig_clean_thread.sh
#   ./scripts/ig_clean_thread.sh 2225236074884360
#   ./scripts/ig_clean_thread.sh --list
#   ./scripts/ig_clean_thread.sh --curl-tests
#
# Variables (opcionales, también lee .env del repo):
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS
# =============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi

DB_HOST="${DB_HOST:-n8n.yavingos.com}"
DB_PORT="${DB_PORT:-5433}"
DB_NAME="${DB_NAME:-n8ntecbite_db}"
DB_USER="${DB_USER:-postgres}"
DB_PASS="${DB_PASS:-${PGPASSWORD:-}}"
DEFAULT_CONVERSATION_ID="${IG_DEFAULT_CONVERSATION_ID:-2225236074884360}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

usage() {
  cat <<EOF
Limpia hilo de conversación Instagram en Postgres.

Uso:
  $0 [conversation_id]
  $0 --list
  $0 --curl-tests

Ejemplos:
  $0
  $0 2225236074884360
  $0 --curl-tests

Default conversation_id: $DEFAULT_CONVERSATION_ID
EOF
}

require_db_pass() {
  if [[ -z "$DB_PASS" ]]; then
    echo -e "${RED}Error: falta DB_PASS o PGPASSWORD.${NC}" >&2
    exit 1
  fi
}

psql_cmd() {
  PGPASSWORD="$DB_PASS" psql \
    "postgresql://${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}" \
    -P pager=off \
    -v ON_ERROR_STOP=1 \
    "$@"
}

list_recent_threads() {
  require_db_pass
  echo -e "${CYAN}Conversaciones recientes:${NC}"
  psql_cmd -c "
    SELECT
      s.conversation_id,
      s.make,
      s.model,
      s.year,
      s.roof_type,
      s.category,
      s.stage,
      (SELECT COUNT(*) FROM instagram_conversation_event e WHERE e.conversation_id = s.conversation_id) AS events,
      s.updated_at
    FROM instagram_conversation_state s
    ORDER BY s.updated_at DESC
    LIMIT 15;
  "
}

clean_conversation() {
  local conversation_id="$1"
  require_db_pass

  echo -e "${YELLOW}Limpiando hilo:${NC} $conversation_id"

  local before_state before_events
  before_state="$(psql_cmd -At -c "SELECT COUNT(*) FROM instagram_conversation_state WHERE conversation_id = '$conversation_id';")"
  before_events="$(psql_cmd -At -c "SELECT COUNT(*) FROM instagram_conversation_event WHERE conversation_id = '$conversation_id';")"

  if [[ "$before_state" == "0" && "$before_events" == "0" ]]; then
    echo -e "${YELLOW}No hay datos para ese conversation_id.${NC}"
    return 0
  fi

  psql_cmd <<SQL
BEGIN;
DELETE FROM instagram_conversation_event WHERE conversation_id = '$conversation_id';
DELETE FROM instagram_conversation_state WHERE conversation_id = '$conversation_id';
COMMIT;
SQL

  local after_state after_events
  after_state="$(psql_cmd -At -c "SELECT COUNT(*) FROM instagram_conversation_state WHERE conversation_id = '$conversation_id';")"
  after_events="$(psql_cmd -At -c "SELECT COUNT(*) FROM instagram_conversation_event WHERE conversation_id = '$conversation_id';")"

  echo -e "${GREEN}Listo.${NC} Eliminados: state=$before_state, events=$before_events"
  echo -e "${GREEN}Restantes:${NC} state=$after_state, events=$after_events"
}

clean_curl_tests() {
  require_db_pass
  echo -e "${YELLOW}Limpiando hilos de prueba curl-* ...${NC}"
  local ids
  ids="$(psql_cmd -At -c "SELECT conversation_id FROM instagram_conversation_state WHERE conversation_id LIKE 'curl-%' ORDER BY updated_at DESC;")"
  if [[ -z "$ids" ]]; then
    echo -e "${YELLOW}No hay hilos curl-* para limpiar.${NC}"
    return 0
  fi
  while IFS= read -r id; do
    [[ -n "$id" ]] && clean_conversation "$id"
  done <<< "$ids"
}

main() {
  case "${1:-}" in
    -h|--help|help)
      usage
      ;;
    --list|-l)
      list_recent_threads
      ;;
    --curl-tests)
      clean_curl_tests
      ;;
    "")
      clean_conversation "$DEFAULT_CONVERSATION_ID"
      ;;
    *)
      clean_conversation "$1"
      ;;
  esac
}

main "$@"
