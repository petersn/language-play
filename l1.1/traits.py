#!/usr/bin/python

import copy
import UnionFind
import inference
import core

class TypeExpr(inference.HashableMixin):
	"""TypeExpr

	Represents a type, potentially with variables as holes.
	"""
	def __init__(self, kind, contents):
		assert kind in ("var", "app")
		self.kind = kind
		self.contents = contents

	def key(self):
		return self.kind, tuple(self.contents)

	def __repr__(self):
		if self.kind == "var":
			name, = self.contents
			return "?%s" % (name,)
		elif self.kind == "app":
			return "%s{%s}" % (
				self.contents[0].name,
				", ".join(repr(type_arg) for type_arg in self.contents[1:]),
			)
		raise NotImplementedError("Unhandled: %r" % (self.kind,))

	def apply_type_subs(self, type_subs):
		if self in type_subs:
			return type_subs[self]
		if self.kind == "app":
			return TypeExpr(
				self.kind,
				[self.contents[0]] + [
					type_arg.apply_type_subs(type_subs)
					for type_arg in self.contents[1:]
				],
			)
		return self

class TraitExpr(inference.HashableMixin):
	"""TraitExpr

	Represents a trait, potentially with types in it that themselves have variables as holes.
	A trait with a variable as a hole might occur in a type bound.
	"""
	def __init__(self, base_trait, type_parameters):
		assert isinstance(base_trait, TraitDef)
		assert isinstance(type_parameters, list)
		assert all(isinstance(i, TypeExpr) for i in type_parameters)
		self.base_trait = base_trait
		self.type_parameters = type_parameters

	def key(self):
		return self.base_trait, tuple(self.type_parameters)

	def __repr__(self):
		return "%s{%s}" % (
			self.base_trait.name,
			", ".join(type_param for type_param in self.type_parameters),
		)

	def apply_type_subs(self, type_subs):
		return TraitExpr(self.base_trait, [
			type_param.apply_type_subs(type_subs)
			for type_param in self.type_parameters
		])


class TypeBound(inference.HashableMixin):
	def __init__(self, ty, trait):
		self.ty = ty
		self.trait = trait

	def key(self):
		return self.ty, self.trait

	def __repr__(self):
		return "%s: %s" % (self.ty, self.trait)

class BlockDef(inference.HashableMixin):
	def __init__(self, name, args, bounds):
		assert isinstance(name, str)
		assert all(isinstance(i, TypeExpr) for i in args)
		assert all(isinstance(i, TypeBound) for i in bounds)
		self.name = name
		self.args = args
		self.bounds = bounds

	def key(self):
		return self.name, tuple(self.args), tuple(self.bounds)

	def __repr__(self):
		return "%s %s<%s> [%s]" % (
			self.block_name,
			self.name,
			", ".join(str(arg) for arg in self.args),
			", ".join(str(bound) for bound in self.bounds),
		)

class DataDef(BlockDef):
	block_name = "data"

class TraitDef(BlockDef):
	block_name = "trait"

class Impl:
	def __init__(self, quantified_args, bounds, trait_expr, type_expr):
		assert all(isinstance(i, TypeExpr) for i in quantified_args)
		assert all(isinstance(i, TypeBound) for i in bounds)
		assert isinstance(trait_expr, TraitExpr)
		assert isinstance(type_expr, TypeExpr)
		self.quantified_args = quantified_args
		self.bounds = bounds
		self.trait_expr = trait_expr
		self.type_expr = type_expr

	def get_fresh(self, ctx):
		"""get_fresh() -> (TraitExpr, [TypeBound])
		
		Returns a tuple of:
		0) The trait expression except with all quantified over type variables being replaced with fresh ones.
		1) A list of the type bounds, but with the same substitution applied.
		"""
		subs = {arg: ctx.new_type() for arg in self.quantified_args}
		return [
		]
		return s

	def __repr__(self):
		return "impl<%s> %s for %s [%s]" % (
			", ".join(str(arg) for arg in self.quantified_args),
			self.trait_expr,
			self.type_expr,
			", ".join(str(bound) for bound in self.bounds),
		)

class SolverContext:
	def __init__(self):
		self.next_type_variable = 0
		self.var_unions = UnionFind.UnionFind()

	def copy(self):
		new_context = SolverContext()
		new_context.next_type_variable = self.next_type_variable
		new_context.type_unions = self.type_unions.copy()

	def new_type(self):
		self.next_type_variable += 1
		return TypeExpr("var", [str(self.next_type_variable)])

class TraitSolver:
	def __init__(self):
		self.datas = []
		self.traits = []
		self.impls = []

	def check(self, ctx, trait_expr, type_expr):
		assert isinstance(trait_expr, TraitExpr)
		assert isinstance(type_expr, TypeExpr)
		print "Checking %s for %s" % (trait_expr, type_expr)
		for impl in self.impls:
			self.unify_traits(ctx, trait_expr, impl.trait_expr)

	def unify_traits(self, ctx, trait_expr1, trait_expr2):
		print "Unifying traits:", trait_expr1, " == ", trait_expr2
		if trait_expr1.base_trait != trait_expr2.base_trait:
			print "CANNOT unify; different base traits."
			return
		for t1, t2 in zip(trait_expr1.type_parameters, trait_expr2.type_parameters):
			self.unify_types(t1, t2)

	def unify_types(self, ctx, type_expr1, type_expr2):
		print "Unifying types:", type_expr1, " == ", type_expr2
		ctx.equate_types

#		print trait_expr1, "unify", trait_expr2

#		print "Attempting to check (%s) for (%s)" % (trait, ty)
#		for impl in self.impls:
#			if self.could_impl(ctx, impl, trait, ty):
#				print impl

#	def could_impl(self, ctx, impl, trait, ty):
#		print "Testing (%s) against (%s) for (%s)" % (impl, trait, ty)
#		print impl.trait_expr.base_trait
#		print impl.trait_expr, "  <==>  ", trait
#		print impl.type_expr, "  <==>  ", ty

if __name__ == "__main__":
	solver = TraitSolver()
	# Define the builtin types.
	X = TypeExpr("var", ["X"])
	Num = DataDef("Num", [], [])
	Str = DataDef("Str", [], [])
	Vec = DataDef("Vec", [X], [])
	Clone = TraitDef("Clone", [], [])

	solver.datas.append(Num)
	solver.datas.append(Str)
	solver.datas.append(Vec)
	solver.traits.append(Clone)

	# Make Num clonable.
	solver.impls.append(Impl(
		[],
		[],
		TraitExpr(Clone, []),
		TypeExpr("app", [Num]),
	))
#	solver.impls.append(Impl(
#		[],
#		[],
#		TraitExpr(Magical, []),
#		TypeExpr("app", [Wizard])
#	))

	ctx = SolverContext()
	solver.check(ctx, TraitExpr(Clone, []), TypeExpr("app", [Num]))

