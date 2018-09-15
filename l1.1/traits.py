#!/usr/bin/python

import copy
import UnionFind
import inference
import core

class TraitExpr(inference.HashableMixin):
	"""TraitExpr

	Represents a trait, potentially with types in it that themselves have variables as holes.
	A trait with a variable as a hole might occur in a type bound.
	"""
	def __init__(self, base_trait, type_parameters):
		assert isinstance(base_trait, TraitDef)
		assert isinstance(type_parameters, list)
		assert all(isinstance(i, inference.MonoType) for i in type_parameters)
		self.base_trait = base_trait
		self.type_parameters = type_parameters

	def key(self):
		return self.base_trait, tuple(self.type_parameters)

	def __repr__(self):
		return "%s{%s}" % (
			self.base_trait.name,
			", ".join(str(type_param) for type_param in self.type_parameters),
		)

	def apply_type_subs(self, type_subs):
		return TraitExpr(self.base_trait, [
			type_param.apply_type_subs(type_subs)
			for type_param in self.type_parameters
		])

class TypeBound(inference.HashableMixin):
	def __init__(self, ty, trait):
		assert isinstance(ty, inference.MonoType)
		assert isinstance(trait, TraitExpr)
		self.ty = ty
		self.trait = trait

	def key(self):
		return self.ty, self.trait

	def __repr__(self):
		return "%s: %s" % (self.ty, self.trait)

	def apply_type_subs(self, type_subs):
		return TypeBound(
			self.ty.apply_type_subs(type_subs),
			self.trait.apply_type_subs(type_subs),
		)

class BlockDef(inference.HashableMixin):
	def __init__(self, name, args, bounds, cookie=None):
		assert isinstance(name, str)
		assert all(isinstance(i, inference.MonoType) for i in args)
		assert all(isinstance(i, TypeBound) for i in bounds)
		self.name = name
		self.args = args
		self.bounds = bounds
		self.cookie = cookie

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
	def __init__(self, quantified_args, bounds, trait_expr, type_expr, cookie=None):
		assert all(isinstance(i, inference.MonoType) for i in quantified_args)
		assert all(isinstance(i, TypeBound) for i in bounds)
		assert isinstance(trait_expr, TraitExpr)
		assert isinstance(type_expr, inference.MonoType)
		self.quantified_args = quantified_args
		self.bounds = bounds
		self.trait_expr = trait_expr
		self.type_expr = type_expr
		self.cookie = cookie

	def get_fresh(self, ctx):
		"""get_fresh() -> ([TypeBound], TraitExpr, inference.MonoType)
		
		Returns a tuple of:
		1) A list of the type bounds, but with the substitution applied.
		2) The trait expression except with all quantified over type variables being replaced with fresh ones.
		3) The type expression the impl is for, but with the same substitution applied.
		"""
		subs = {arg: ctx.new_type() for arg in self.quantified_args}
		return (
			[bound.apply_type_subs(subs) for bound in self.bounds],
			self.trait_expr.apply_type_subs(subs),
			self.type_expr.apply_type_subs(subs),
		)

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
		self.unification_context = inference.UnificationContext()
		self.all_bounds = []

	def copy(self):
		new_context = SolverContext()
		new_context.next_type_variable = self.next_type_variable
		new_context.unification_context = self.unification_context.copy()
		new_context.all_bounds = self.all_bounds[:]
		return new_context

	def new_type(self):
		self.next_type_variable += 1
		return inference.MonoType("var", "?" + str(self.next_type_variable))

class TraitSolver:
	def __init__(self):
		self.datas = []
		self.traits = []
		self.impls = []

	def check(self, ctx, trait_expr, type_expr):
		assert isinstance(trait_expr, TraitExpr)
		assert isinstance(type_expr, inference.MonoType)
		print "Checking %s for %s" % (trait_expr, type_expr)
		for impl in self.impls:
			print "  Testing:", impl
			new_ctx = ctx.copy()
			# In order to see if we can possibly use this impl we need to accumulate all relevant bounds.
			fresh_bounds, fresh_trait, fresh_type = impl.get_fresh(new_ctx)
			try:
				self.unify_traits(new_ctx, trait_expr, fresh_trait)
				self.unify_types(new_ctx, type_expr, fresh_type)
			except inference.UnificationError, e:
				print "      Unification error:", e
				continue
			new_ctx.all_bounds.extend(fresh_bounds)
			if self.check_bounds(new_ctx):
				return impl
		print "Failed to find an impl!"

	def check_bounds(self, ctx):
		print "    Checking bounds."
		for bound in ctx.all_bounds:
			specific_type = ctx.unification_context.most_specific_type(bound.ty)
			print "      Bound: %s: %s" % (specific_type, bound.trait)
			if not self.check(SolverContext(), bound.trait, specific_type):
				print "Recursive check failed!"
				return False
		return True

	def unify_traits(self, ctx, trait_expr1, trait_expr2):
		print "    Unifying traits:", trait_expr1, " == ", trait_expr2
		if trait_expr1.base_trait != trait_expr2.base_trait:
			print "      CANNOT unify; different base traits."
			return
		for t1, t2 in zip(trait_expr1.type_parameters, trait_expr2.type_parameters):
			self.unify_types(t1, t2)

	def unify_types(self, ctx, type_expr1, type_expr2):
		print "    Unifying types:", type_expr1, " == ", type_expr2
		ctx.unification_context.equate(type_expr1, type_expr2)

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
	X = inference.MonoType("var", "?X")
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
		inference.MonoType("link", [], link_name="Num"),
	))
	solver.impls.append(Impl(
		[X],
		[
			TypeBound(X, TraitExpr(Clone, [])),
		],
		TraitExpr(Clone, []),
		inference.MonoType("link", [X], link_name="Vec")
	))

	ctx = SolverContext()
	has_trait = solver.check(
		ctx,
		TraitExpr(Clone, []),
#		inference.MonoType("link", [], link_name="Str"),
		inference.MonoType("link", [
			inference.MonoType("link", [], link_name="Num"),
		], link_name="Vec"),
	)
	print "Result:", has_trait

