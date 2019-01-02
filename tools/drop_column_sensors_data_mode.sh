#!/usr/bin/env bash

SQL_FILE=$1

sqlite3 "${SQL_FILE}" <<EOF
BEGIN TRANSACTION;
CREATE TEMPORARY TABLE sensors_backup (
        id VARCHAR(255) NOT NULL,
        protocol VARCHAR(20),
        address VARCHAR(255),
        sensor_type VARCHAR(20),
        status INTEGER,
        icon VARCHAR(50),
        PRIMARY KEY (id)
);
INSERT INTO sensors_backup SELECT id, protocol, address, sensor_type, status, icon FROM sensors;
DROP TABLE sensors;
CREATE TABLE sensors (
        id VARCHAR(255) NOT NULL,
        protocol VARCHAR(20),
        address VARCHAR(255),
        sensor_type VARCHAR(20),
        status INTEGER,
        icon VARCHAR(50),
        PRIMARY KEY (id)
);
INSERT INTO sensors SELECT * FROM sensors_backup;
DROP TABLE sensors_backup;
COMMIT;
EOF

$(dirname $0)/migrate stamp head
