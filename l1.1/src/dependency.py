#!/usr/bin/python

import collections

class DependencyManager:
	def __init__(self):
		self.dependencies = collections.defaultdict(set)

	def add_dep(self, a, b):
		"""add_dep(a, b) -> make a dependend on b"""
		self.dependencies[a].add(b)
		self.dependencies[b]

	def strongly_connected_components(self):
		index = {}
		low_link = {}
		on_stack = collections.defaultdict(bool)
		next_index = [0]
		scc = []
		stack = []
		components = []

		def strong_connect(node):
			index[node] = low_link[node] = next_index[0]
			next_index[0] += 1
			stack.append(node)
			on_stack[node] = True

			for dep in self.dependencies[node]:
				if dep not in index:
					strong_connect(dep)
					low_link[node] = min(low_link[node], low_link[dep])
				elif on_stack[dep]:
					# index[] rather than low_link[] in the next line is intentional.
					low_link[node] = min(low_link[node], index[dep])

			if low_link[node] == index[node]:
				scc[:] = []
				while True:
					w = stack.pop()
					on_stack[w] = False
					scc.append(w)
					if w == node:
						break
				components.append(scc[:])

		for node in self.dependencies:
			if node not in index:
				strong_connect(node)
		self.sanity_check(components)
		return components

	def sanity_check(self, components):
		# Compute the time at which each node is defined.
		times = {}
		for i, component in enumerate(components):
			for node in component:
				times[node] = i
		# Demand that each node is defined no earlier than all its deps.
		for node, deps in self.dependencies.iteritems():
			for dep in deps:
				assert times[dep] <= times[node]

if __name__ == "__main__":
	g = DependencyManager()
	g.add_dep("a", "b")
	g.add_dep("b", "c")
	g.add_dep("d", "a")
	g.add_dep("c", "b")
	components = g.strongly_connected_components()
	for comp in components:
		print comp

