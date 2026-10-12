#!/bin/sh
set -eu
cd /vol1/docker/heybox-checkin
# 保留最后一次容器启动输出，避免 cron 输出无限增长。
umask 077
exec /usr/bin/docker compose run --rm -T heybox > logs/last-run.log 2>&1
