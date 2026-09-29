#!/usr/bin/env bash
# ============================================================
#  First-deploy acceptance test - run INSIDE the lab VM:
#      scp D:\lab\guest\mysql-first-deploy.sh lab:~/    (from Windows)
#      ssh lab
#      chmod +x mysql-first-deploy.sh && ./mysql-first-deploy.sh
#  Deploys MySQL like a real server, then from the Windows host
#  connect with Navicat:  host=lab (or 192.168.100.10) user=root pass=123456
# ============================================================
set -e

echo '[1/4] apt update + install mysql-server (aliyun mirror, fast) ...'
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server

echo '[2/4] listen on all interfaces (real server style) ...'
sudo sed -i 's/^bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf

echo '[3/4] create remote root (lab-internal network only, safe) ...'
sudo mysql -e "CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED WITH caching_sha2_password BY '123456'; GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION; FLUSH PRIVILEGES;"

echo '[4/4] restart + status ...'
sudo systemctl restart mysql
sudo systemctl status mysql --no-pager | head -n 6

echo ''
echo 'DONE. From Windows host -> Navicat:  host=lab  port=3306  user=root  pass=123456'
echo 'This VM is only reachable from THIS computer (NAT 192.168.100.0/24), not from LAN/internet.'
