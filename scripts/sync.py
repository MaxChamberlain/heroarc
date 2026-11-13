#!/usr/bin/env python3
"""Run this on a schedule (README: cron). Optional: --days 60 for a first backfill."""
import sys, oura_sync
days = int(sys.argv[sys.argv.index('--days') + 1]) if '--days' in sys.argv else 14
print(oura_sync.sync(days))
