#!/usr/bin/python

import sys
import UnionFind

class HashableMixin:
	def __eq__(self, other):
		return self.key() == other.key()

	def __hash__(self):
		return hash(self.key())

class MonoType(HashableMixin):
	def __init__(self, kind, contents, link_name=None):
		assert kind in ("link", "var")
		self.kind = kind
		self.contents = contents
		self.link_name = link_name

	def key(self):
		return self.kind, tuple(self.contents), self.link_name

	def __repr__(self):
		if self.kind == "var":
			return self.contents
		else:
			return "<%s%s>" % (
				self.link_name,
				"".join(" " + str(c) for c in self.contents),
			)

	def apply_type_subs(self, type_subs):
		if self in type_subs:
			return type_subs[self]
		if self.kind == "link":
			return MonoType(
				self.kind,
				[
					c.apply_type_subs(type_subs)
					for c in self.contents
				],
				link_name=self.link_name,
			)
		return self

class PolyType(HashableMixin):
	def __init__(self, binders, mono):
		assert isinstance(binders, set)
		assert all(isinstance(binder, MonoType) and binder.kind == "var" for binder in binders)
		assert isinstance(mono, MonoType)
		self.binders = binders
		self.mono = mono

	def key(self):
		return frozenset(self.binders), self.mono

	def __repr__(self):
		return "(forall %s, %s)" % (
			" ".join(str(i) for i in sorted(self.binders)),
			self.mono,
		)

class Expr(HashableMixin):
	def __init__(self, kind, contents):
		assert kind in ("var", "app", "abs", "let")
		self.kind = kind
		self.contents = contents

	def key(self):
		return self.kind, tuple(self.contents)

	def __repr__(self):
		if self.kind == "var":
			return "%s" % (self.contents,)
		return "(%s%s)" % (
			self.kind,
			"".join(" " + str(c) for c in self.contents),
		)

def free_type_variables(x):
	"""free_type_variables(x) -> set of variables (as MonoTypes with kind="var")

	The argument x must either be a MonoType, PolyType, or list thereof.
	Returns all free type variables in the argument.
	"""
	if isinstance(x, MonoType):
		if x.kind == "var":
			return set([x])
		elif x.kind == "link":
			return free_type_variables(x.contents)
	elif isinstance(x, PolyType):
		return free_type_variables(x.mono) - set(x.binders)
	elif isinstance(x, list):
		v = set()
		for entry in x:
			v |= free_type_variables(entry)
		return v
	print x
	assert False

class UnificationError(Exception):
	pass

class UnificationContext:
	def __init__(self):
		self.unions = UnionFind.UnionFind()
		self.union_set_links = {}

	def copy(self):
		u = UnificationContext()
		u.unions = self.unions.copy()
		u.union_set_links = self.union_set_links.copy()
		return u

	def equate(self, t1, t2):
		"""equate(t1, t2) -> None

		Add the constraint that the t1 and t2 type expressions must be equal.
		Critically, if either t1 or t2's current union sets contains a link then we recursively union the respective links.
		"""
		assert isinstance(t1, MonoType)
		assert isinstance(t2, MonoType)
#		print "Equating:", t1, t2
		# TODO: Add occurs check!

		# Canonicalize our types into existing union sets.
		t1, t2 = self.unions[t1], self.unions[t2]
		# Union together the two types, links or not.
		self.unions.union(t1, t2)
		# If a term is a link then it becomes a union set link.
		for t in (t1, t2):
			if t.kind == "link":
				self.union_set_links[t] = t
		# If both t1 and t2 have existing union set links then recursively unify them.
		if t1 in self.union_set_links and t2 in self.union_set_links:
			l1, l2 = self.union_set_links[t1], self.union_set_links[t2]
			assert l1.kind == l2.kind == "link"
			if len(l1.contents) != len(l2.contents) or l1.link_name != l2.link_name:
				raise UnificationError("Cannot unify %r with %r" % (l1, l2))
			for a, b in zip(l1.contents, l2.contents):
				self.equate(a, b)
		# If at least one of the two has a union set link then store it as the new union set link for them both.
		# We don't have to worry about which one we picked because we just recursively equated the two.
		for t in (t1, t2):
			if t in self.union_set_links:
				self.union_set_links[self.unions[t1]] = self.union_set_links[t]

	def must_equal(self, t1, t2):
		return self.unions[t1] == self.unions[t2]

	def most_specific_type(self, t):
		t = self.unions[t]
		# If the union set contains a link, then we consider that more specific than a variable, so use that instead.
		if t in self.union_set_links:
			t = self.union_set_links[t]
		# Recursively make the type specific.
		if t.kind == "link":
			return MonoType(
				"link",
				[self.most_specific_type(x) for x in t.contents],
				link_name=t.link_name,
			)
		return t

class Inference:
	def __init__(self):
		self.unification_context = UnificationContext()
		self.type_counter = 0

	def inst(self, poly_t):
		"""inst(poly_t: PolyType) -> a new MonoType

		Takes every bound variable in poly_t, and assigns it a new type variable, and returns a new MonoType with the substitution applied.
		"""
		assert isinstance(poly_t, PolyType)
		subst = {bound_variable: self.new_type() for bound_variable in poly_t.binders}
		def replace(t):
			if t.kind == "var":
				return subst.get(t, t)
			else:
				return MonoType(
					"link",
					map(replace, t.contents),
					link_name=t.link_name,
				)
		return replace(poly_t.mono)

	def new_type(self):
		self.type_counter += 1
		return MonoType("var", "t%i" % (self.type_counter,))

	def contextual_generalization(self, gamma, t):
		"""contextual_generalization(gamma, t: MonoType) -> PolyType

		Returns the generalization of t (a MonoType) as a PolyType, with every free variable of t not elsewhere used in the context gamma universally quantified.
		"""
		assert isinstance(t, MonoType)
		return PolyType(
			free_type_variables(t) - free_type_variables(gamma.values()),
			t,
		)

	def J(self, gamma, expr, depth=0):
#		print "  "*depth, "Inf:", expr
		result = self._J(gamma, expr, depth=depth)
#		print "  "*depth, "->", result, "=", expr
		return result

	def _J(self, gamma, expr, depth=0):
		if expr.kind == "var":
			if expr in gamma:
				return self.inst(gamma[expr])
			raise ValueError("Unknown variable: %r" % (expr,))
		elif expr.kind == "app":
			# Get types for the two parts.
			fn = expr.contents[0]
			fn_type = self.J(gamma, fn, depth=depth+1)
			args = expr.contents[1:]
			arg_types = [self.J(gamma, arg, depth=depth+1) for arg in args]
			# Create a new type, and add an equation.
			result_type = self.new_type()
			self.unification_context.equate(fn_type, MonoType("link", arg_types + [result_type], link_name="fun"))
			return result_type
		elif expr.kind == "abs":
			args = expr.contents[:-1]
			result_expr = expr.contents[-1]
			assert all(arg.kind == "var" for arg in args)
			# Do inference on the result expression, in a context where the argument has a fresh type.
			arg_types = [self.new_type() for _ in args]
			gamma_prime = gamma.copy()
			for arg, arg_type in zip(args, arg_types):
				gamma_prime[arg] = PolyType(set(), arg_type)
			result_type = self.J(gamma_prime, result_expr, depth=depth+1)
			return MonoType("link", arg_types + [result_type], link_name="fun")
		elif expr.kind == "let":
			# TODO: Let polymorphism.
			var, expr1, expr2 = expr.contents
			assert var.kind == "var"
			# Do inference on the variable's expression.
			var_t = self.J(gamma, expr1, depth=depth+1)
			# Contextually generalize the variable's type.
			var_poly_t = self.contextual_generalization(gamma, var_t)
			# Do inference on the resultant expression, in a context where the variable has the given value.
			gamma_prime = gamma.copy()
			gamma_prime[var] = var_poly_t
			return self.J(gamma_prime, expr2, depth=depth+1)
		raise NotImplementedError("Not handled: %r" % (expr,))

if __name__ == "__main__":
	a = MonoType("var", "a")
	b = MonoType("var", "b")
	c = MonoType("var", "c")
	t_int = MonoType("link", [], link_name="int")
	t_bool = MonoType("link", [], link_name="bool")
	t1 = MonoType("link", [a, t_int], link_name="fun")

	print t1

	inf = Inference()
	inf.unification_context.equate(a, c)
	inf.unification_context.equate(b, t_bool)
	inf.unification_context.equate(a, b)

	print inf.unification_context.most_specific_type(c)

	e1 = Expr("let", [
		Expr("var", "id"),
		Expr("abs", [
			Expr("var", "x"),
			Expr("var", "x")
		]),
		Expr("var", "id")
	])

	e5 = Expr("abs", [
		Expr("var", "m"),
		Expr("let", [
			Expr("var", "y"),
			Expr("var", "m"),
			Expr("let", [
				Expr("var", "x"),
				Expr("app", [Expr("var", "y"), Expr("var", "flag")]),
				Expr("var", "x")
			])
		])
	])

	print "=== Doing inference."

	inf = Inference()
	final_type = inf.J(
		{
			Expr("var", "flag"): PolyType(set(), MonoType("link", [], link_name="bool")),
		},
		e5,
	)
	print inf.unification_context.most_specific_type(final_type)

