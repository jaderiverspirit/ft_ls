#!/usr/bin/env python3
"""Compare ft_ls with GNU ls (forced to one-name-per-line output)."""
import itertools
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / 'ft_ls'
ENV = dict(os.environ, LC_ALL='C', TZ='UTC', QUOTING_STYLE='literal')


def run(binary, args):
	return subprocess.run([str(binary), *args], text=True, capture_output=True, env=ENV)


def main():
	subprocess.run(['make', '-s', '-C', str(ROOT)], check=True)
	passed = 0
	failures = []
	with tempfile.TemporaryDirectory() as tmp:
		root = Path(tmp)
		(root / 'a').write_text('hello')
		(root / 'b').write_text('world')
		(root / '.hidden').write_text('secret')
		(root / 'empty').mkdir()
		(root / 'nested').mkdir()
		(root / 'nested' / 'deep').mkdir()
		(root / 'nested' / 'deep' / 'data').write_text('data')
		(root / 'link').symlink_to('a')
		(root / 'broken').symlink_to('not_here')
		(root / 'dirlink').symlink_to('nested')
		os.mkfifo(root / 'pipe')
		os.chmod(root / 'b', 0o751)
		opts = 'lRart'
		tests = [[str(root)], [str(root / 'a')],
				 [str(root / 'a'), str(root / 'nested')],
				 [str(root / 'dirlink')],
				 [str(root / 'broken')],
				 [str(root / 'missing')],
				 [str(root / 'empty'), str(root / 'nested')]]
		for size in range(6):
			for combo in itertools.combinations(opts, size):
				flag = '-' + ''.join(combo) if combo else None
				for args in tests:
					argv = ([flag] if flag else []) + args
					# GNU ls uses -1 to suppress columns, ft_ls always uses one per line.
					expected = run('ls', ['-1', *argv])
					actual = run(BINARY, argv)
					# Padding differences for mixed dir/file long listings are allowed
					# by the subject; whitespace is normalized for this comparison.
					normalize = lambda s: [' '.join(line.split()) for line in s.splitlines()]
					if normalize(expected.stdout) != normalize(actual.stdout) \
							or expected.returncode != actual.returncode:
						failures.append((argv, expected.stdout, actual.stdout,
										 expected.returncode, actual.returncode))
					else:
						passed += 1
	print(f'Passed: {passed}; failed: {len(failures)}')
	for argv, expected, actual, exp_status, status in failures[:10]:
		print('FAIL', argv, 'statuses:', exp_status, status)
		print('expected:', repr(expected[:400]))
		print('actual:  ', repr(actual[:400]))
	raise SystemExit(bool(failures))


if __name__ == '__main__':
	main()
