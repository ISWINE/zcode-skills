#!/usr/bin/env bash
# ============================================================
#  mysql-install.sh - enterprise-trimmed MySQL 8 for the lab VM
#  Run inside VM:  bash ~/mysql-install.sh
#
#  Profile: MySQL Community (GPLv2, free for commercial use),
#  InnoDB-only diet, hardening baseline, replication-ready.
#  Trimmed: MyISAM / MEMORY / ARCHIVE / BLACKHOLE / FEDERATED
#           engines disabled; X Protocol (33060) off.
#  Kept:    InnoDB (data) + CSV (server log tables need it) +
#           PERFORMANCE_SCHEMA (built-in, cannot be disabled).
# ============================================================
set -e
CNF=/etc/mysql/mysql.conf.d/zz-lab-enterprise.cnf

echo '[1/6] apt install mysql-server (community 8.0)'
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server

echo '[2/6] stop for tuning'
sudo systemctl stop mysql

echo "[3/6] write enterprise config: $CNF"
sudo rm -f /etc/mysql/mysql.conf.d/99-lab-enterprise.cnf
sudo tee "$CNF" > /dev/null <<'EOF'
# ============================================================
#  enterprise-trimmed MySQL 8 (community) - lab profile
# ============================================================
[mysqld]
# ---- storage engine diet ----
# InnoDB = data; CSV = required by server log tables;
# PERFORMANCE_SCHEMA = built-in monitoring (not disablable).
disabled_storage_engines = MyISAM,MEMORY,ARCHIVE,BLACKHOLE,FEDERATED
# ---- X Protocol off (33060; classic 3306 is all we use) ----
mysqlx = OFF
# ---- innodb core (dedicated small server) ----
innodb_buffer_pool_size        = 1G
innodb_redo_log_capacity       = 512M
innodb_flush_method            = O_DIRECT
innodb_flush_log_at_trx_commit = 1
innodb_io_capacity             = 1000
innodb_io_capacity_max         = 2000
# ---- network & security baseline ----
bind-address    = 0.0.0.0
# zz- prefix: this file is read LAST and wins over distro mysqld.cnf (digits sort before letters)
skip-name-resolve
max_connections = 200
local_infile    = 0
# ---- observability ----
slow_query_log  = ON
long_query_time = 1
# ---- replication-ready (enterprise standard) ----
server_id                 = 1
gtid_mode                 = ON
enforce_gtid_consistency  = ON
binlog_expire_logs_seconds = 259200
EOF

echo '[4/6] start + enable'
sudo systemctl start mysql
sudo systemctl enable mysql > /dev/null 2>&1

echo '[5/6] harden accounts (lab: remote root for Navicat, NAT-isolated)'
sudo mysql -e "DELETE FROM mysql.user WHERE User=''; DROP DATABASE IF EXISTS test; FLUSH PRIVILEGES;"
sudo mysql -e "CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED WITH caching_sha2_password BY '123456'; GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION; FLUSH PRIVILEGES;"

echo '[6/6] receipt'
sudo mysql -e "SELECT @@version AS version, @@version_comment AS edition;"
echo '--- engine diet (behavior proof, SHOW ENGINES does NOT reflect the gate) ---'
sudo mysql -N -e "SELECT CONCAT('  disabled_storage_engines = ', @@disabled_storage_engines);"
sudo mysql -e "CREATE DATABASE IF NOT EXISTS _t;"
if sudo mysql -e "CREATE TABLE _t.x(id INT) ENGINE=MyISAM" 2>/dev/null; then
  echo '  FAIL: MyISAM creation unexpectedly SUCCEEDED'
else
  echo '  OK: CREATE ... ENGINE=MyISAM refused (ERROR 3161 expected)'
fi
sudo mysql -e "DROP DATABASE _t;"
echo '--- X protocol (option, not a runtime variable) ---'
if sudo ss -tln | grep -q ':33060 '; then echo '  WARN: 33060 still listening'; else echo '  OK: X protocol off (33060 closed)'; fi
echo '--- key settings ---'
sudo mysql -N -e "SELECT CONCAT('  buffer_pool  = ', @@innodb_buffer_pool_size/1024/1024, 'M');"
sudo mysql -N -e "SELECT CONCAT('  redo_log     = ', @@innodb_redo_log_capacity/1024/1024, 'M');"
sudo mysql -N -e "SELECT CONCAT('  gtid_mode    = ', @@gtid_mode);"
echo '--- listening ---'
sudo ss -tln | grep -E ':3306 ' || echo '  WARN: 3306 not listening'
echo '--- service ---'
systemctl is-active mysql
echo DONE
