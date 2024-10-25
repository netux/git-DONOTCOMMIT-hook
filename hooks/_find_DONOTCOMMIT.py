#!/usr/bin/env python3

import os
import sys
import re
import subprocess
from dataclasses import dataclass
from typing import Generator, Dict, Tuple, List

@dataclass
class DiffChange:
	at: Tuple
	before: List[str]
	after: List[str]

@dataclass
class Diff:
	from_path: str
	to_path: str
	changes: List[DiffChange]

class DiffReader:
	_gen: Generator[str, None, None]
	_line: str

	def __init__(self, txt: str):
		self._gen = txt.split('\n').__iter__()

	def next(self) -> str:
		self._line = next(self._gen)
		return self._line

	def _read_change(self, dest: DiffChange) -> None:
		while True:
			self.next()
			if self._line.startswith('+'):
				dest.after.append(self._line[1:])
			elif self._line.startswith('-'):
				dest.before.append(self._line[1:])
			elif self._line.startswith(' ') or self._line.startswith('\\'):
				pass
			else:
				break

	def _read_changes(self) -> List[DiffChange]:
		result = []
		while True:
			if not self._line.startswith('@'):
				break
			m = re.match(r'@+ [+-]\d+(?:,\d+)? [+-]\d+(?:,\d+)? @+', self._line)
			if m is None:
				self.next()
				continue
			change = DiffChange(before=[], after=[], at=m[0])
			self._read_change(change)
			result.append(change)
		return result


	def parse(self) -> Diff:
		result = []
		self.next()
		while True:
			try:
				m = re.match(r'^diff --git ((?:\w+)/(?:.+)) ((?:\w+)/(?:.+))', self._line)
				if m is None:
					self.next()
					continue

				(file1_path, file2_path) = m.groups()
				self.next() # new file mode...
				if self._line.startswith('new file mode'):
					self.next()
				if self._line.startswith('old mode'):
					self.next()
				if self._line.startswith('new mode'):
					self.next()
				if self._line.startswith('index'):
					self.next()

				from_path: str = None
				to_path: str = None

				m = re.match(r'\-\-\- (.+)', self._line)
				if m is not None:
					(from_path,) = m.groups()
					self.next()
				m = re.match(r'\+\+\+ (.+)', self._line)
				if m is not None:
					(to_path,) = m.groups()
					self.next()

				changes = self._read_changes()
				result.append(Diff(from_path=from_path, to_path=to_path, changes=changes))
			except StopIteration:
				break

		return result

def contains_DONOTCOMMIT(text: str) -> bool:
	return (
		'start DONOTCOMMIT' in text or \
		'region DONOTCOMMIT' in text or \
		'mark DONOTCOMMIT' in text
	)

proc = subprocess.run(['git', 'diff', '--cached'], capture_output=True)
diffs = DiffReader(proc.stdout.decode('utf-8')).parse()

flagged = False
for diff in diffs:
	for change in diff.changes:
		if any(contains_DONOTCOMMIT(line) for line in change.after):
			print(f'DONOTCOMMIT section found @ {diff.to_path} {change.at}')
			print('\n'.join((f'+{line}' for line in change.after)))
			flagged = True

sys.exit(1 if flagged else 0)
