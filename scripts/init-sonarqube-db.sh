#!/bin/sh
set -eu

SONAR_DB_NAME="${SONARQUBE_DB_NAME:-sonarqube}"

db_exists="$(psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${SONAR_DB_NAME}'")"

if [ "$db_exists" = "1" ]; then
    echo "SonarQube database '${SONAR_DB_NAME}' already exists"
    exit 0
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<EOSQL
CREATE DATABASE "${SONAR_DB_NAME}";
EOSQL

echo "Created SonarQube database '${SONAR_DB_NAME}'"
