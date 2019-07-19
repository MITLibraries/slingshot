#!/bin/sh
set -e


trap flush_logs EXIT

flush_logs()
{
  code=$?
  echo "slingshot exited with $code"
  echo "Flushing ECS logs"
  sleep 10
  exit $code
}

slingshot "$@"
