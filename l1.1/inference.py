#!/usr/bin/python

import sys
import UnionFind
import dependency
import core
import utils

def alpha_canonicalize(t, subs=None):
	assert isinstance(t, core.MonoType)
	if subs is None:
		subs = {}
	if isinstance(t, core.VarType):
		if t not in subs:
			new_name = str(len(subs) + 1)
			subs[t] = core.VarType(new_name)
		return subs[t]
	elif isinstance(t, core.AppType):
		return core.AppType(
			t.constructor,
			[
				alpha_canonicalize(arg, subs=subs)
				for arg in t.args
			],
		)
	raise NotImplementedError("Unhandled: %r" % (t,))

def alpha_equivalent(t1, t2):
	return alpha_canonicalize(t1) == alpha_canonicalize(t2)

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
		assert isinstance(t1, core.MonoType)
		assert isinstance(t2, core.MonoType)
#		print "Equating:", t1, t2
		# TODO: Add occurs check!

		# Canonicalize our types into existing union sets.
		t1, t2 = self.unions[t1], self.unions[t2]
		# Union together the two types, links or not.
		self.unions.union(t1, t2)
		# If a term is a link then it becomes a union set link.
		for t in (t1, t2):
			if isinstance(t, core.AppType):
				self.union_set_links[t] = t
		# If both t1 and t2 have existing union set links then recursively unify them.
		if t1 in self.union_set_links and t2 in self.union_set_links:
			l1, l2 = self.union_set_links[t1], self.union_set_links[t2]
			assert isinstance(l1, core.AppType) and isinstance(l2, core.AppType)
			if len(l1.args) != len(l2.args) or l1.constructor != l2.constructor:
				raise UnificationError("Cannot unify %r with %r" % (l1, l2))
			for a, b in zip(l1.args, l2.args):
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
		if isinstance(t, core.AppType):
			return core.AppType(
				t.constructor,
				[self.most_specific_type(x) for x in t.args],
			)
		return t

# TODO: XXX: I'm not sure I like this...
# The rationale is that CodeBlocks need a globally unique type variable to represent their return type.
global_type_counter = 0
def global_new_type():
	global global_type_counter
	global_type_counter += 1
	return core.VarType(str(global_type_counter))

class Gamma(object):
	"""Gamma

	Defines a typing context.
	"""
	__slots__ = "context", "return_monotype"

	def __init__(self):
		self.context = {}
		self.return_monotype = None

	def __repr__(self):
		return "%r (ret=%r)" % (self.context, self.return_monotype)

	def __getitem__(self, key):
		return self.context[key]

	def __setitem__(self, key, value):
		assert isinstance(key, core.VarExpr)
		assert isinstance(value, core.PolyType)
		self.context[key] = value

	def __contains__(self, key):
		assert isinstance(key, core.VarExpr)
		return key in self.context

	def copy(self):
		"""copy() -> shallow copy of the context"""
		new_gamma = Gamma()
		new_gamma.context = self.context.copy()
		new_gamma.return_monotype = self.return_monotype
		return new_gamma

class Inference:
	def __init__(self):
		self.unification_context = UnificationContext()
		self.type_counter = 0

	def inst(self, poly_t):
		"""inst(poly_t: PolyType) -> a new MonoType

		Takes every bound variable in poly_t, and assigns it a new type variable, and returns a new MonoType with the substitution applied.
		"""
		assert isinstance(poly_t, core.PolyType)
		subst = {bound_variable: self.new_type() for bound_variable in poly_t.binders}
		return poly_t.mono.apply_type_subs(subst)

	def new_type(self):
		# TODO: XXX: For now...
		return global_new_type()
#		self.type_counter += 1
#		return core.VarType("%i" % (self.type_counter,))

	def contextual_generalization(self, gamma, t):
		"""contextual_generalization(gamma, t: MonoType) -> PolyType

		Returns the generalization of t (a MonoType) as a PolyType, with every free variable of t not elsewhere used in the context gamma universally quantified.
		"""
		assert isinstance(t, core.MonoType)
		all_bound = set()
		for poly_t in gamma.context.values():
			all_bound |= poly_t.free_type_variables()
		return core.PolyType(
			t.free_type_variables() - all_bound,
			t,
		)

	def J(self, gamma, expr, depth=0):
		print "  "*depth, "Inf:", expr, gamma
		result = self._J(gamma, expr, depth=depth)
		print "  "*depth, "->", result, "for", expr
		return result

	def _J(self, gamma, expr, depth=0):
		if isinstance(expr, core.VarExpr):
			if expr in gamma:
				return self.inst(gamma[expr])
			raise ValueError("Unknown variable: %r" % (expr,))
		elif isinstance(expr, core.AppExpr):
			# Get types for the two parts.
			fn_type = self.J(gamma, expr.fn_expr, depth=depth+1)
			arg_types = [self.J(gamma, arg, depth=depth+1) for arg in expr.arg_exprs]
			# Create a new type, and add an equation.
			result_type = self.new_type()
			self.unification_context.equate(
				fn_type,
				core.AppType("fun", arg_types + [result_type]),
			)
			return result_type
		elif isinstance(expr, core.AbsExpr):
			args = [core.VarExpr(arg_name) for arg_name in expr.arg_names]
			# Do inference on the result expression, in a context where the argument has a fresh type.
			arg_types = [self.new_type() for _ in args]
			# TODO: XXX: Unify these with the type annotations from expr.arg_types!
			gamma_prime = gamma.copy()
			for arg, arg_type in zip(args, arg_types):
				gamma_prime[arg] = core.PolyType(set(), arg_type)
			result_type = self.J(gamma_prime, expr.result_expr, depth=depth+1)
			# TODO: XXX: Unify this result type with the type annotation from expr.return_type!
			return core.AppType("fun", arg_types + [result_type])
		elif isinstance(expr, core.LetExpr):
			var = core.VarExpr(expr.name)
			# Do inference on the variable's expression.
			var_t = self.J(gamma, expr.expr1, depth=depth+1)
			var_t = self.unification_context.most_specific_type(var_t)
			# Contextually generalize the variable's type.
			var_poly_t = self.contextual_generalization(gamma, var_t)
			# Do inference on the resultant expression, in a context where the variable has the given value.
			gamma_prime = gamma.copy()
			gamma_prime[var] = var_poly_t
			return self.J(gamma_prime, expr.expr2, depth=depth+1)
		elif isinstance(expr, core.BlockExpr):
			self.infer_code_block(gamma, expr.code_block, depth=depth+1)
			# TODO: Extract the block's return type here.
			# XXX: Is most_specific_type necessary here? Where *is* it necessary?
			return self.unification_context.most_specific_type(expr.code_block.return_monotype)
			#return core.AppType("nil", [])
		raise NotImplementedError("Not handled: %r" % (expr,))

	def infer_code_block(self, gamma, code_block, depth=0):
		# Give the code block a new return type.
		assert code_block.return_monotype == None
		code_block.return_monotype = global_new_type()
		gamma = gamma.copy()
		gamma.return_monotype = code_block.return_monotype

		# Compute which names are provided by which declarations.
		name_provided_by = {}
		for decl in code_block.entries:
			for name in decl.provided_names():
				# TODO: Implement redefinition here later.
				assert name not in name_provided_by, "Redefinition of %r" % (name,)
				name_provided_by[name] = decl

		# Compute dependencies within the block.
		dep_manager = dependency.DependencyManager()
		for decl in code_block.entries:
			for name in decl.name_deps():
				if name in name_provided_by:
					dep_manager.add_dep(decl, name_provided_by[name])
				else:
					# XXX: I'm still not really sure what the interpretation of this is.
					# Maybe I should check that name is in gamma?
					# If it isn't then this is probably an issue?
					print "FREE DEPENDENCY VARIABLE:", name

		# Compute an order to perform inference in.
		strongly_connected_components = dep_manager.strongly_connected_components()
		print "\nStrongly connected components:", strongly_connected_components

		# Throw in every decl that wasn't included in any dep, and therefore isn't in any strongly connected component.
		remaining_decls = set(code_block.entries)
		for component in strongly_connected_components:
			remaining_decls -= set(component)
		print "Remaining:", remaining_decls

		# It really doesn't matter how we throw these remaining decls in, but for now we just add each one as its own component at the end.
		for decl in remaining_decls:
			strongly_connected_components.append([decl])

		print "Inference groups:", strongly_connected_components

		# Compute typing for each strongly connected component together.
		for component in strongly_connected_components:
			name_types = {}
			print "=== Inference for component:", component

			# Add fresh monotype variables to our system for the names declared in this component.
			for decl in component:
				for name in decl.provided_names():
					new_type_var = name_types[name] = self.new_type()
					gamma[core.VarExpr(name)] = core.PolyType(set(), new_type_var)

			# Apply inference, and add constraints on our monotype variables.
			for decl in component:
				if isinstance(decl, core.Declaration):
					type_expr = self.J(gamma, decl.expr, depth=depth+1)
					self.unification_context.equate(name_types[decl.name], type_expr)
				elif isinstance(decl, core.ReturnStatement):
					type_expr = self.J(gamma, decl.expr, depth=depth+1)
					# TODO: XXX: Appropriately unify with a return type variable.
					self.unification_context.equate(gamma.return_monotype, type_expr)
				else:
					raise NotImplementedError("unhandled decl in inference: %r" % (decl,))

			# Generalize the monotypes into polytypes, and update the context.
			# We ignore a subset of the CodeBlock.Entry types, because they have no additional info to propagate.
			ignored_types = (core.ReturnStatement,)
			for decl in component:
				if isinstance(decl, core.Declaration):
					type_var = name_types[decl.name]
					poly_type = self.contextual_generalization(
						gamma,
						self.unification_context.most_specific_type(type_var),
					)
					gamma[core.VarExpr(decl.name)] = poly_type
					# Store the inferred type into the Declaration.
					decl.type_annotation = poly_type
				elif isinstance(decl, ignored_types):
					pass
				else:
					raise NotImplementedError("unhandled decl in inference: %r" % (decl,))

			print "Gamma:", gamma

		# Replace the return monotype with the most specific available.
		code_block.return_monotype = self.unification_context.most_specific_type(code_block.return_monotype)

