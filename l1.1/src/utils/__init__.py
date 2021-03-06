#!/usr/bin/python
"""
utils/__init__.py

Simple shared functionality and snippets.
"""

from UnionFind import *

def indent(depth, s):
	return "\n".join(
		" " * depth + line if line else line
		for line in s.split("\n")
	)

class StringBuilder:
	def __init__(self):
		self.contents = []
		self.depth = 0
		self.indent_state = False

	def indent(self, amount=2):
		class WithContext:
			def __init__(self, closed_self):
				self.closed_self = closed_self
			def __enter__(self):
				self.closed_self.depth += amount
			def __exit__(self, ty, value, traceback):
				self.closed_self.depth -= amount
		return WithContext(self)

	def _write(self, s):
		self.contents.append(s)

	def write_no_newlines(self, s):
		assert "\n" not in s
		if not s:
			return
		if self.indent_state:
			self._write(" " * self.depth)
			self.indent_state = False
		self._write(s)

	def write_newline(self):
		self._write("\n")
		self.indent_state = True

	def write(self, s):
		# TODO: Make this non-stupid with split.
		for c in s:
			if c != "\n":
				self.write_no_newlines(c)
			else:
				self.write_newline()
#		for line in s.split("\n"):
#			self.write_no_newlines(line)
#		print "CALL:", repr(s)
#		for line in s.split("\n"):
#			print "RAW:", repr(line)
#			self.write_no_newlines(line)
#			self._write("\n")
#			self.indent_state = True
#		self.contents.append(indent(self.depth, s))

	def __str__(self):
		return "".join(self.contents)

def pretty(obj):
	b = StringBuilder()
	obj.pretty(b)
	return b

class HashableMixin:
	def __eq__(self, other):
		return self.__class__ is other.__class__ and self.key() == other.key()

	def __ne__(self, other):
		return not (self == other)

	def __hash__(self):
		return hash(self.key())

if __name__ == "__main__":
	b = StringBuilder()
	print >>b, "Hello"
	with b.indent(2):
		print >>b, "World!"
	print repr(str(b))

