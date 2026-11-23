#!/usr/bin/env bash
# Polls <url>/health until it returns 200 and the expected version, or fails
# after <timeout> seconds. A cold start (container from zero, database resuming
# from pause) can take a minute or two, so the default allows 5 minutes.
#   infra/wait-healthy.sh <base-url> <expected-sha> [timeout-seconds]
set -uo pipefail
url=$1
sha=$2
deadline=$((SECONDS + ${3:-300}))
while ((SECONDS < deadline)); do
  response=$(curl -s --max-time 60 -w '\n%{http_code}' "$url/health")
  status=${response##*$'\n'}
  body=${response%$'\n'*}
  echo "$(date -u +%H:%M:%S) $status $body"
  if [[ $status == 200 && $body == *"\"version\":\"$sha\""* ]]; then
    echo "healthy: $url"
    exit 0
  fi
  sleep 10
done
echo "::error::$url/health did not return 200 with version $sha in time"
exit 1
