#!/usr/bin/env bash
# lab guest one-shot system report (read-only, safe to run any time)
echo "hostname      : $(hostname)"
echo "kernel        : $(uname -r)"
grep PRETTY_NAME /etc/os-release | sed 's/PRETTY_NAME=//; s/"//g; s/^/os            : /'
echo "uptime        : $(uptime -p)"
echo "cloud-init    : $(cloud-init status 2>&1)"
echo "ip            : $(ip -4 addr show eth0 | awk '/inet /{print $2}')"
echo "gateway       : $(ip route | awk '/default/{print $3; exit}')"
echo "dns           : $(resolvectl status 2>/dev/null | awk '/DNS Servers/{print $3; exit}')"
echo "root fs       : $(df -h / | awk 'NR==2{print $2 " total, " $3 " used, " $4 " free"}')"
echo "memory        : $(free -m | awk 'NR==2{print $2 " MB total"}') (dynamic, host balloons 0.5-4G)"
echo "ntp synced    : $(timedatectl show -p NTPSynchronized --value 2>/dev/null)"
echo "timezone      : $(timedatectl show -p Timezone --value 2>/dev/null)"
echo "failed units  : $(systemctl --failed --no-legend 2>/dev/null | wc -l)"
echo "pkgs installed: $(dpkg -l | grep -c '^ii')"
echo "apt source    : $(grep -h -m1 '^URIs' /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null | cut -d' ' -f2-)"
echo "ssh host key  : $(ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub 2>/dev/null | awk '{print $1, $2}')"
echo "mysql         : $(if dpkg -s mysql-server >/dev/null 2>&1; then echo installed, $(systemctl is-active mysql); else echo not-installed; fi)"
