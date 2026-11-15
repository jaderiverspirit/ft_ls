#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
make -s
printf 'Baseline: \n'; ./ft_ls src
printf '\nLong, recursive and all: \n'; ./ft_ls -laR src
printf '\nUnknown flag (expected failure):\n'; if ./ft_ls -z; then exit 1; fi
printf '\nMissing path (expected failure):\n'; if ./ft_ls nonexistent_test_path; then exit 1; fi
