#!/usr/bin/python
# encoding: utf-8

import sys

# Horrific hack workaround to deal with cyclic import.
if __name__ == "__main__":
	sys.modules["easy"] = sys.modules["__main__"]

import enum, collections
import easy_parse

class HashableMixin:
	def __eq__(self, other):
		return self.__class__ is other.__class__ and self.key() == other.key()

	def __ne__(self, other):
		return not (self == other)

	def __hash__(self):
		return hash(self.key())

@enum.unique
class EvalStrategy(enum.Enum):
	WHNF = 1 # Evaluate to Weak Head Normal Form.
	CBV  = 2 # Evaluate by Call By Value.

class TypeCheckFailure(Exception):
	pass

class Context:
	class WithHandler:
		def __init__(self, this):
			self.this = this

		def __enter__(self):
			self.this.depth += 1

		def __exit__(self, ty, value, traceback):
			self.this.depth -= 1

	def __init__(self):
		self.typings = {}
		self.definitions = {}
		self.inductives = {}
		self.depth = 0

	def __repr__(self):
		return "<ctx: %s %s>" % (self.typings, self.definitions)

	def copy(self):
		new_ctx = Context()
		new_ctx.typings = self.typings.copy()
		new_ctx.definitions = self.definitions.copy()
		new_ctx.inductives = self.inductives.copy()
		new_ctx.depth = self.depth
		return new_ctx

	def prefix(self):
		return "  " * self.depth

	def depth_scope(self):
		return Context.WithHandler(self)

	def contains_ty(self, var):
		assert isinstance(var, Var)
		return var in self.typings

	def contains_def(self, var):
		assert isinstance(var, Var)
		return var in self.definitions

	def lookup_ty(self, var):
		assert isinstance(var, Var)
		return self.typings[var]

	def lookup_def(self, var):
		assert isinstance(var, Var)
		return self.definitions[var]

	def extend_ty(self, var, ty, in_place=False):
		assert isinstance(var, Var)
		assert isinstance(ty, Term)
		assert var not in self.definitions
		ctx = self if in_place else self.copy()
		ctx.typings[var] = ty
		return ctx

	def extend_def(self, var, term, in_place=False):
		assert isinstance(var, Var)
		assert isinstance(term, Term)
		assert var not in self.typings
		ctx = self if in_place else self.copy()
		ctx.definitions[var] = term
		return ctx

class Parameters:
	def __init__(self, names, types):
		assert len(names) == len(types)
		assert all(isinstance(name, str) for name in names)
		assert all(isinstance(ty, Term) for ty in types)
		self.names = names
		self.types = types

	def __len__(self):
		assert len(self.names) == len(self.types)
		return len(self.names)

	def wrap_with(self, term, wrapper):
		for name, ty in zip(self.names, self.types)[::-1]:
			term = wrapper(Var(name), ty, term)
		return term

	def wrap_with_products(self, term):
		return self.wrap_with(term, DependentProduct)

	def wrap_with_abstractions(self, term):
		return self.wrap_with(term, Abstraction)

	def extend_context_with_typing(self, ctx):
		ctx = ctx.copy()
		for name, ty in zip(self.names, self.types):
			ctx = ctx.extend_ty(Var(name), ty, in_place=True)
		return ctx

	def __repr__(self):
		return " ".join(
			"(%s : %s)" % (name, ty)
			for name, ty in zip(self.names, self.types)
		)

class Inductive:
	class Constructor:
		def __init__(self, ty, base_ty):
			"""__init__(self, ty, base_ty)

			ty is the actual overall type of the constructor.
			base_ty is the type of the constructor as written in the Inductive definition, before it was wrapped with a product over the inductive's parameters.
			"""
			assert isinstance(ty, Term)
			assert isinstance(base_ty, Term)
			self.ty = ty
			self.base_ty = ty

	def __init__(self, ctx, name, parameters, arity):
		assert isinstance(name, str)
		assert isinstance(parameters, Parameters)
		assert isinstance(arity, Term)
		self.name = name
		self.parameters = parameters
		self.arity = arity
		self.constructors = collections.OrderedDict()

		# Check the arity is appropriately a product ending in a sort.
		# XXX: Is the inductive itself allowed in the arity anywhere?
		self.check_arity(arity)

		assert name not in ctx.inductives, "Cannot redefine inductive."
		ctx.inductives[name] = self

		self.computed_type = self.parameters.wrap_with_products(self.arity)

	def check_arity(self, arity):
		# A sort is always a valid arity.
		if arity.is_sort():
			return
		assert isinstance(arity, DependentProduct), "Arities must be a product terminating with a sort."
		self.check_arity(arity.result_ty)

	def add_constructor(self, con_name, base_ty):
		# XXX: Here's the really weird rule about how parameters wrap every constructor with products.
		# I think this is right? It's really hard to find a description online that's clear.
		ty = self.parameters.wrap_with_products(base_ty)
		self.constructors[con_name] = Inductive.Constructor(ty, base_ty)
		# XXX: TODO: Check positivity!
		# This is necessary for consistency!

	def pprint(self):
		print "Inductive %s %s: %s :=" % (self.name, self.parameters, self.arity)
		for con_name, con in self.constructors.iteritems():
			print "  | %s : %s" % (con_name, con.ty)

# ===== Define term ilks =====

class Term(HashableMixin):
	def key(self): raise NotImplementedError
	def __repr__(self): raise NotImplementedError
	def normalize(self, ctx, strategy): raise NotImplementedError
	def free_vars(self): raise NotImplementedError
	# If you're implementing a subclass also add handling to AlphaCanonicalizer.

	def infer(self, ctx):
		# NB: It might be helpful to add ctx.typings.keys(), ctx.definitions.keys() to the debug printing.
		print ctx.prefix() + "?", self
		with ctx.depth_scope():
			ty = self.do_infer(ctx)
		print ctx.prefix() + "=", ty
		return ty

	def check(self, ctx, ty):
		print ctx.prefix() + "Check:", self, ":", ty
		with ctx.depth_scope():
			inferred_type = self.infer(ctx)
			if not compare_terms(ctx, inferred_type, ty):
				raise TypeCheckFailure("Failure to match: %r != %r" % (inferred_type, ty))
		print ctx.prefix() + "Pass!"

	def subst(self, x, y):
		return self

	def is_sort(self):
		return False

class Annotation(Term):
	def __init__(self, term, ty):
		self.term = term
		self.ty = ty

	def key(self):
		return self.term, self.ty

	def __repr__(self):
		return "(%s :: %s)" % (self.term, self.ty)

	def subst(self, x, y):
		return Annotation(self.term.subst(x, y), self.ty.subst(x, y))

	def normalize(self, ctx, strategy):
		return Annotation(
			self.term.normalize(ctx, strategy),
			self.ty.normalize(ctx, strategy),
		)

	def do_infer(self, ctx):
		# XXX: This might not be right.
		# XXX: Universe polymorphism missing!
		self.ty.check(ctx, SortType(0))
		self.term.check(ctx, self.ty), "Type annotation failed!"
		return self.ty

	def free_vars(self):
		# XXX: Should the annotation be included in free variables?
		# Hmm...
		return self.term.free_vars() | self.ty.free_vars()

class SortType(Term):
	def __init__(self, universe_index):
		assert isinstance(universe_index, int)
		assert universe_index >= 0
		self.universe_index = universe_index

	def key(self):
		return self.universe_index

	def __repr__(self):
		subscript_digits = {"%i" % (i,): "\xe2\x82" + chr(0x80 + i) for i in xrange(10)}
		return "\xf0\x9d\x95\x8b%s" % ("".join(subscript_digits[c] for c in str(self.universe_index)),)

	def normalize(self, ctx, strategy):
		return self

	def do_infer(self, ctx):
		# XXX: FIXME: I'm currently overriding the predicativity of the Type universes!
		# This opens up Girard's paradox, but I don't care for right now.
		return SortType(0)
#		return SortType(self.universe_index + 1)

	def check(self, ctx, ty):
		# XXX: Implement universe cumulativity here!
		# FIXME: Currently this code forces Type{i} : Type{i}
		if ty != self:
			raise TypeCheckFailure("Failure to match: %r != %r" % (ty, self))

	def free_vars(self):
		return set()

	def is_sort(self):
		return True

class SortProp(SortType):
	def __init__(self):
		pass

	def key(self):
		return

	def __repr__(self):
		return "\xe2\x84\x99"

	def do_infer(self, ctx):
		# Implement Prop : Type
		return SortType(0)

class Var(Term):
	def __init__(self, var):
		assert isinstance(var, str)
		self.var = var

	def key(self):
		return self.var

	def __repr__(self):
		return self.var

	def subst(self, x, y):
		if self == x:
			return y
		return self

	def normalize(self, ctx, strategy):
		if ctx.contains_def(self):
			return ctx.lookup_def(self).normalize(ctx, strategy)
		# XXX: This should be an error!
		# We need a separate atom type soon.
		return self

	def do_infer(self, ctx):
		if ctx.contains_ty(self):
			return ctx.lookup_ty(self)
		elif ctx.contains_def(self):
			return ctx.lookup_def(self).infer(ctx)
		print "BAD CONTEXT:", ctx
		raise RuntimeError("Unbound variable: %r" % (self,))

	def free_vars(self):
		return set([self])

class DependentProduct(Term):
	def __init__(self, var, var_ty, result_ty):
		assert isinstance(var, Var)
		assert isinstance(var_ty, Term)
		assert isinstance(result_ty, Term)
		self.var = var
		self.var_ty = var_ty
		self.result_ty = result_ty

	def key(self):
		return self.var, self.var_ty, self.result_ty

	def __repr__(self):
		# Check if the variable is used at all.
		if self.var not in self.result_ty.free_vars():
			return "(%s \xe2\x86\x92 %s)" % (self.var_ty, self.result_ty)
		return "(\xe2\x88\x80 %s : %s . %s)" % (self.var, self.var_ty, self.result_ty)

	def subst(self, x, y):
		# For now don't handle this case, as it means we were probably inappropriately alpha-sensitive.
		assert x != self.var
		return DependentProduct(
			self.var,
			self.var_ty.subst(x, y),
			self.result_ty.subst(x, y),
		)

	def normalize(self, ctx, strategy):
		return self
#		return DependentProduct(self.var, self.var_ty.normalize(ctx, strategy), self.res_ty.normalize(ctx, strategy))

	def do_infer(self, ctx):
		# Check all the types.
		# XXX: Universe polymorphism needed here!
		# XXX: Is inference here rather than checking problematic?
		var_ty = self.var_ty.infer(ctx)
		assert var_ty.is_sort()
#		self.var_ty.check(ctx, SortType(0))
		result_sort = self.result_ty.infer(ctx.extend_ty(self.var, self.var_ty))
		assert result_sort.is_sort()
		# XXX: Deal with universes appropriately here.
		return result_sort #SortType(0)

	def check(self, ctx, ty):
		return self.infer(ctx) == ty

	def free_vars(self):
		return self.var_ty.free_vars() | (self.result_ty.free_vars() - set([self.var]))

class Abstraction(Term):
	def __init__(self, var, var_ty, result):
		assert isinstance(var, Var)
		self.var = var
		self.var_ty = var_ty
		self.result = result

	def key(self):
		return self.var, self.var_ty, self.result

	def __repr__(self):
		return "(\xce\xbb %s : %s . %s)" % (self.var, self.var_ty, self.result)

	def subst(self, x, y):
		if x == self.var:
			# This rule is important:
			# If we're substituting y for x, and our current variable is x, then we
			# block the substitution for proceeding any further in our result,
			# because in our result x is freshly lexically bound. However, we must
			# substitute y for x in our variable's type, because in its type it's
			# still using the old binding for x.
			return Abstraction(
				self.var,
				self.var_ty.subst(x, y),
				self.result,
			)
		return Abstraction(
			self.var,
			self.var_ty.subst(x, y),
			self.result.subst(x, y),
		)

	def normalize(self, ctx, strategy):
		return self
#		return Abstraction(self.var, self.var_ty.normalize(ctx, strategy), self.result.normalize(ctx, strategy))

	def do_infer(self, ctx):
		# XXX: Universe polymorphism needed here!
		var_sort = self.var_ty.infer(ctx)
		assert var_sort.is_sort()
#		self.var_ty.check(ctx, SortType(0))
		ctx = ctx.extend_ty(self.var, self.var_ty)
		u = self.result.infer(ctx)
		# XXX: Do I need to abstract over self.var somehow?
		return DependentProduct(self.var, self.var_ty, u)

	def free_vars(self):
		return self.var_ty.free_vars() | (self.result.free_vars() - set([self.var]))

class Application(Term):
	def __init__(self, fn, arg):
		self.fn = fn
		self.arg = arg

	def key(self):
		return self.fn, self.arg

	def __repr__(self):
		return "(%s %s)" % (self.fn, self.arg)

	def subst(self, x, y):
		return Application(self.fn.subst(x, y), self.arg.subst(x, y))

	def normalize(self, ctx, strategy):
		fn = self.fn.normalize(ctx, strategy)
		arg = self.arg
		if strategy == EvalStrategy.CBV:
			arg = arg.normalize(ctx, strategy)
		# If our function isn't concrete, then early out.
		if not isinstance(fn, Abstraction):
			return Application(fn, arg)
		# Perform a substitution.
		instantiation = fn.result.subst(fn.var, arg)
		return instantiation.normalize(ctx, strategy)

	def do_infer(self, ctx):
		fn_type = self.fn.infer(ctx)
		fn_type = coerce_to_product(ctx, fn_type)
		self.arg.check(ctx, fn_type.var_ty)
		return fn_type.result_ty.subst(fn_type.var, self.arg)

	def free_vars(self):
		return self.fn.free_vars() | self.arg.free_vars()

class InductiveRef(Term):
	def __init__(self, name):
		self.name = name

	def key(self):
		return self.name

	def __repr__(self):
		return "%%%s" % (self.name,)

	def normalize(self, ctx, strategy):
		return self

	def do_infer(self, ctx):
		return ctx.inductives[self.name].computed_type

	def free_vars(self):
		return set()

	def get_inductive(self, ctx):
		return ctx.inductives[self.name]

class ConstructorRef(Term):
	def __init__(self, name, con_name):
		self.name = name
		self.con_name = con_name

	def key(self):
		return self.name, self.con_name

	def __repr__(self):
		return "%s::%s" % (self.name, self.con_name)

	def normalize(self, ctx, strategy):
		return self

	def do_infer(self, ctx):
		return self.get_constructor(ctx).ty

	def free_vars(self):
		return set()

	def get_inductive(self, ctx):
		return ctx.inductives[self.name]

	def get_constructor(self, ctx):
		return self.get_inductive(ctx).constructors[self.con_name]

class Fix(Term):
	def __init__(self, recursive_name, params, ty, body):
		assert isinstance(recursive_name, str)
		assert isinstance(params, Parameters)
		assert isinstance(ty, Term)
		assert isinstance(body, Term)
		self.recursive_var = Var(recursive_name)
		self.params = params
		self.ty = ty
		self.body = body

	def key(self):
		return self.recursive_var, self.params, self.ty, self.body

	def __repr__(self):
		return "fix %s %s : %s := %s" % (
			self.recursive_var,
			self.params,
			self.ty,
			self.body,
		)

	def normalize(self, ctx, strategy):
		# XXX: FIXME: The current strategy here is to eta-expand one level of the Fix.
		# This is a *terrible* solution, and probably just doesn't work.
		# An unapplied Fix should be considered to in normal form already.
		# We need to extend Application to know about a Fix.
		function_term = self.params.wrap_with_abstractions(self.body)
		# XXX: The following extend_def is totally bogus and does nothing.
#		# Give a reference to the recursive Fix to our child.
#		ctx = ctx.extend_def(self.recursive_var, self)
		print "Function term:", function_term
		return function_term.normalize(ctx, strategy)

	def overall_type(self, ctx):
		return self.params.wrap_with_products(self.ty)

	def do_infer(self, ctx):
		# XXX: FIXME: No primitive recursiveness checking yet!
		# This makes the theory trivially unsound via: (fix f (x : False) : False := f x) : False

		overall_type = self.overall_type(ctx)

		# Build our recursive context in which self.recursive_var is assumed to have the right fixed type.
		ctx = ctx.extend_ty(self.recursive_var, overall_type)
		# Also assume our arguments have the given types.
		ctx = self.params.extend_context_with_typing(ctx)
		# Now check that our result has the right type.
		self.body.check(ctx, self.ty)
		return overall_type

	def free_vars(self):
		return set()

class Match(Term):
	class Arm(HashableMixin):
		def __init__(self, pattern, result):
			self.pattern = pattern
			self.result = result
			self.pattern_head, self.pattern_args = extract_app_spine(pattern)
			# Demand that the pattern variables are all variables.
			assert all(isinstance(i, Var) for i in self.pattern_args)

		def key(self):
			return self.pattern, self.result

		def __repr__(self):
			return "| %s => %s" % (self.pattern, self.result)

		def subst(self, x, y):
			# XXX: Subtle binding here to double-check!
			result = self.result if x in self.pattern_args else self.result.subst(x, y)
			return Match.Arm(
				self.pattern.subst(x, y),
				result,
			)

		def free_vars(self):
			return self.result.free_vars() - set(self.pattern_args)

	def __init__(self, matchand, as_term, in_term, return_term, arms):
		assert all(isinstance(arm, Match.Arm) for arm in arms)
		self.matchand = matchand
		self.as_term = as_term
		self.in_term = in_term
		self.return_term = return_term
		self.arms = tuple(arms)

	def key(self):
		return self.matchand, self.as_term, self.in_term, self.return_term, self.arms

	def __repr__(self):
		return "match %s as %s in %s return %s with%s end" % (
			self.matchand,
			self.as_term,
			self.in_term,
			self.return_term,
			"".join(" %s" % (arm,) for arm in self.arms),
		)

	def subst(self, x, y):
		# We have to be careful again about captures because the arms form bindings, as do the as_term and in_term clauses.
		# XXX: FIXME: How should I handle as_term, in_term, return_term?
		return Match(
			self.matchand.subst(x, y),
			self.as_term.subst(x, y),
			self.in_term.subst(x, y),
			self.return_term.subst(x, y),
			[arm.subst(x, y) for arm in self.arms],
		)

	def normalize(self, ctx, strategy):
		# Here's where we do complicated stuff!
		matchand = self.matchand.normalize(ctx, strategy)
		head, args = extract_app_spine(matchand)
		if not isinstance(head, ConstructorRef):
			# XXX: TODO: If we're evaluating CBV we should reduce some of the other terms too.
			return Match(
				matchand,
				self.as_term,
				self.in_term,
				self.return_term,
				self.arms,
			)
		# Do the pattern matching!
		# Sanity check that all the arms are from the same inductive, and pull out the inductive they're from.
		inductives = set(arm.pattern_head.get_inductive(ctx) for arm in self.arms)
		if not inductives:
			raise ValueError("How the hell did we get an actual value into a well-formed match with no arms (i.e. inhabitant of ⊥) during normalization!? This should only occur from unsoundness! ⊥-inhabitant was: %s" % (head,))
		if len(inductives) > 1:
			raise ValueError("Sanity-check failure: A well-formed match should only have one inductive represented across its arms!")
		inductive, = inductives

		# Find the matching arm.
		for arm in self.arms:
			if arm.pattern_head == head:
				assert len(arm.pattern_args) == len(args), "We should have been ill-typed if we hit this assert!"
				# Bind the pattern variables against the values held in the constructor application.
				ctx = ctx.copy()
				for var, value in zip(arm.pattern_args, args):
					ctx.extend_def(var, value, in_place=True)
				return arm.result.normalize(ctx, strategy)

		raise ValueError("Sanity-check failure: How did our supposedly well-formed match fail to be exhaustive?")

	def get_return_type(self, ctx):
		if self.return_term != Hole():
			return self.return_term
		# If our return type is Hole then infer from our first arm.
		# XXX: Later when we have no arms instead infer our return type as False.
		return self.arms[0].result.infer(ctx)

	def do_infer(self, ctx):
		return_ty = self.get_return_type(ctx)

		# First check that (matchand : I pars t_1 ... t_p)
		# Where pars are our parameters, and the t_1 through t_p saturate the arity.
		matchand_ty = self.matchand.infer(ctx).normalize(ctx, EvalStrategy.WHNF)
		matchand_ty_head, matchand_ty_args = extract_app_spine(matchand_ty)
		assert isinstance(matchand_ty_head, InductiveRef), "Bad matchand ilk: %s" % (matchand_ty,)

		# XXX: Check that the inductive in question (matchand_ty_head) is referencing the right inductive!
		inductive = matchand_ty_head.get_inductive(ctx)

		# Now we check that our return_ty actually resolves to a sort appropriately.
		# First we need to construct the appropriate type to ascribe to our as_term variable which is available to return_ty.
		# The key detail is that this type is (I pars y_1 ... y_p), where pars is filled in by the type
		# inferred for the matchand, and where y_1 through y_p are determined by the in_term.
		# This is a little bit complicated, but just how it works.
		# Therefore, we want our as_term_type to be the inductive (I) applied first to the pars from matchand_ty_args, then to the arity-saturating part of in_term.
		pars = matchand_ty_args[:len(inductive.parameters)]
		_, in_args = extract_app_spine(self.in_term)
		_, arity_tys = extract_product_spine(inductive.arity)
		assert len(in_args) == len(arity_tys), "Extended match's in term must have exactly the same number of arguments as number of arguments in the inductive's arity (not its parameters!)"

		as_term_type = form_app_spine(form_app_spine(matchand_ty_head, pars), in_args)
		print "As term type:", as_term_type
		# We now have formed as_term_type = (I pars y_1 ... y_p)

		# We now need to extract the types for each of the named parameters in the in_term.
		return_ctx = ctx.copy()
		for arg, ty in zip(in_args, arity_tys):
			return_ctx.extend_ty(arg, ty, in_place=True)
		return_ctx.extend_ty(self.as_term, as_term_type, in_place=True)

		# This corresponds to the second line in the typing rule on the bottom of page 7 of this document:
		#     https://hal.inria.fr/hal-01094195/document (Introduction to the Calculus of Inductive constructions)
		# Namely, the requirement that is written:
		#      y_1 \dots y_p, x : I pars y_1 \dots y_p \vdash P : s'
		return_sort = return_ty.infer(return_ctx)
		assert return_sort.is_sort()

		# Check that we have exactly one arm for each constructor of our inductive.
		arm_constructors = collections.Counter(arm.pattern_head for arm in self.arms)
		all_constructors = collections.Counter(
			ConstructorRef(inductive.name, cons_name)
			for cons_name in inductive.constructors
		)
		assert arm_constructors == all_constructors, "Arms of match failed to be exhaustive and mutually-exclusive! %r != %r" % (arm_constructors, all_constructors)

		# Check that every arm is well-typed.
		for arm in self.arms:
			constructor = arm.pattern_head.get_constructor(ctx)
			# We now pull out the constructor args (x_1 : A_1) ... (x_n : A_n) (from the above paper).
			_, cons_args_tys = extract_product_spine(constructor.base_ty)

			arm_ctx = ctx.copy()
			for arg, ty in zip(arm.pattern_args, cons_args_tys):
				arm_ctx.extend_ty(arg, ty, in_place=True)

			# Next we pull out the arity-saturating (the u_1 ... u_p from the paper) of the arguments to the inductive at end of the constructor's type.
			tail = get_product_tail(constructor.base_ty)
			tail_head, tail_args = extract_app_spine(tail)

			# NB: These next two asserts should technically be redundant with the well-formedness checks that occur when the inductive was formed.
			# TODO: Evaluate if I want to do these at all.

			# We normalize in this check because tail_head will be a var in general.
			assert tail_head.normalize(ctx, EvalStrategy.WHNF) == InductiveRef(inductive.name), "Bad constructor head: %r (BUG BUG BUG: This should have been ruled out when the inductive was formed.)" % (tail,)

			# The number of tail args should be exactly len(params) + len(arity).
			assert len(tail_args) == len(inductive.parameters) + len(arity_tys), "Malformed tail in inductive constructor! (BUG BUG BUG: This should have been caught when the inductive was formed.)"

			# These are the u_1 ... u_p from the paper.
			arity_saturating_ind_app_args = tail_args[-len(arity_tys):]
			assert len(in_args) == len(arity_saturating_ind_app_args) == len(arity_tys)

			demanded_type = return_ty
			for arg, ty in zip(in_args, arity_saturating_ind_app_args):
				demanded_type = demanded_type.subst(arg, ty)
			demanded_type = demanded_type.subst(
				self.as_term,
				form_app_spine(arm.pattern_head, arm.pattern_args),
			)

			# Do the well-typedness check on the arm's body.
			# This corresponds to the final line above the solidus on the typing rule for match at the bottom of page 7 of the paper.
			arm.result.check(arm_ctx, demanded_type)

		# Extract t_1 ... t_p from the paper.
		matchand_arity_saturating = matchand_ty_args[-len(arity_tys):]

		# Compute the final (dependent) return type.
		final_return_type = return_ty
		assert len(in_args) == len(matchand_arity_saturating)
		for arg, ty in zip(in_args, matchand_arity_saturating):
			final_return_type.subst(arg, ty)
		final_return_type = final_return_type.subst(self.as_term, self.matchand)

		# XXX: TODO: I'm *really* worried that the above code has a bug due to substitution potentially clashing with other variables, or maybe shadowing/capturing something.
		# I should really just totally ban unbound variables in the AST...

		return final_return_type

	def free_vars(self):
		# XXX: This is probably wrong, as the as_term and in_term parts form bindings that should eliminate free variables from the return_term part.
		root_free = reduce(lambda x, y: x | y, [
			i.free_vars()
			for i in [self.matchand, self.as_term, self.in_term, self.return_term]
		])
		arms_free = set()
		for arm in self.arms:
			arms_free |= arm.free_vars(ctx)
		return root_free | arms_free

class Axiom(Term):
	def __init__(self, ty):
		self.ty = ty

	def key(self):
		return self.ty

	def __repr__(self):
		return "<axiom : %s>" % (self.ty,)

	def subst(self, x, y):
		return self

	def normalize(self, ctx, strategy):
		# XXX: No need to normalize self.ty?
		return self

	def do_infer(self, ctx):
		return self.ty

	def free_vars(self):
		# XXX: No need to recurse into self.ty?
		return set()

class Hole(Term):
	def __init__(self, identifier=""):
		assert isinstance(identifier, str)
		self.identifier = identifier

	def key(self):
		return self.identifier

	def __repr__(self):
		return "_%s" % (self.identifier,)

	def subst(self, x, y):
		return self

	def normalize(self, ctx, strategy):
		return self

	def do_infer(self, ctx):
		raise NotImplementedError("Type inference cannot currently handle holes.")

	def free_vars(self):
		return set()

# ===== End term ilks =====

def extract_app_spine(term):
	assert isinstance(term, Term)
	if isinstance(term, Application):
		head, args = extract_app_spine(term.fn)
		return head, args + [term.arg] # XXX: Quadratic time. :(
	return term, []

def form_app_spine(fn, args):
	for arg in args:
		fn = Application(fn, arg)
	return fn

# FIXME: Make this return a Parameters, and simplify the code base.
def extract_product_spine(term):
	assert isinstance(term, Term)
	if isinstance(term, DependentProduct):
		# XXX: Quadratic time. :(
		variables, tys = extract_product_spine(term.result_ty)
		return [term.var] + variables, [term.var_ty] + tys
	return [], []

def get_product_tail(term):
	assert isinstance(term, Term)
	while isinstance(term, DependentProduct):
		term = term.result_ty
	return term

def compare_terms(ctx, t1, t2):
	t1 = t1.normalize(ctx, EvalStrategy.CBV)
	t2 = t2.normalize(ctx, EvalStrategy.CBV)
	# TODO: Maybe implement the additional rules that Spartan TT does?
	return alpha_equivalent(ctx, t1, t2)

def coerce_to_product(ctx, term):
	assert isinstance(term, Term)
	term = term.normalize(ctx, EvalStrategy.WHNF)
	assert isinstance(term, DependentProduct), "Bad product: %r" % (term,)
	return term

class AlphaCanonicalizer:
	def __init__(self, ctx):
		# We need to make sure to not be alpha-indifferent to variables that are actually bound in the context, so map every context variable to itself.
		self.subs = {}
		for var in ctx.typings:
			self.subs[var] = var
		for var in ctx.definitions:
			self.subs[var] = var
		self.next_var_counter = 0

	def new_var(self):
		self.next_var_counter += 1
		return Var("$%s" % (self.next_var_counter,))

	def canonicalize(self, t):
		assert isinstance(t, Term), "Bad object: %r (%r)" % (t, type(t))
		if isinstance(t, Var):
			if t not in self.subs:
				self.subs[t] = self.new_var()
			return self.subs[t]
		elif isinstance(t, Annotation):
			return Annotation(
				self.canonicalize(t.term),
				self.canonicalize(t.ty),
			)
		elif isinstance(t, (DependentProduct, Abstraction)):
			# There is an important case here.
			# We need the following two expressions to canonicalize the same:
			#   (fun x : T . (fun x : T . x))
			#   (fun x : T . (fun y : T . y))
			# If we naively canonicalize here we will mess this up.
			# We want to canonicalize them both to:
			#   (fun $1 : $2 . (fun $3 : $2 . $3))
			# Therefore, we temporarily unbind our knowledge of t.var, if it's bound.
			saved_subs = None
			if t.var in self.subs:
				saved_subs = self.subs.copy()
				self.subs.pop(t.var)
			if isinstance(t, DependentProduct):
				return DependentProduct(
					self.canonicalize(t.var),
					self.canonicalize(t.var_ty),
					self.canonicalize(t.result_ty),
				)
			else:
				return Abstraction(
					self.canonicalize(t.var),
					self.canonicalize(t.var_ty),
					self.canonicalize(t.result),
				)
			if saved_subs != None:
				self.subs = saved_subs
		elif isinstance(t, Application):
			return Application(
				self.canonicalize(t.fn),
				self.canonicalize(t.arg),
			)
		elif isinstance(t, (SortType, SortProp, InductiveRef, ConstructorRef, Axiom, Hole)):
			return t
		raise NotImplementedError("Unhandled: %r" % (t,))

def alpha_canonicalize(ctx, term):
	canonicalizer = AlphaCanonicalizer(ctx)
	return canonicalizer.canonicalize(term)

def alpha_equivalent(ctx, t1, t2):
	return alpha_canonicalize(ctx, t1) == alpha_canonicalize(ctx, t2)

"""
class HoleFiller:
	def fill(self, t):
		assert isinstance(t, Term), "Bad object: %r (%r)" % (t, type(t))
		if isinstance(t, (Var, InductiveRef, ConstructorRef)):
			# These nodes need no further processing.
			pass
		elif isinstance(t, Annotation):
			self.fill(t.term)
			self.fill(t.ty)
		elif isinstance(t, (DependentProduct, Abstraction)):
			self.fill(t.var)
			self.fill(t.var_ty)
			if isinstance(t, DependentProduct):
				self.fill(t.result_ty)
			else:
				self.fill(t.result)
		elif isinstance(t, Abstraction):
			self.fill(t.fn)
			self.fill(t.arg)
		elif isinstance(t, Match):
			if t.return_term == Hole:
				# XXX: Here I'm assuming the match has at least one arm.
				# Once I have a canonical False type then infer False if there are no arms.
				t.return_term = t.arms[0].infer
		elif isinstance(t, Hole):
			raise ValueError("HoleFiller reached a hole it can't fill!")
		else:
			raise NotImplementedError("Unhandled: %r" % (t,))
"""

parse = easy_parse.parse_term

if __name__ == "__main__":
	ctx = Context()
	nat = Inductive(
		ctx,
		"nat",
		Parameters([], []),
		parse("Type0"),
#		Parameters(["T"], [parse("Type0")]),
#		parse("(forall x : T . Type0)"),
	)
	nat.add_constructor("O", parse("nat"))
	nat.add_constructor("S", parse("(forall _ : nat . nat)"))
	nat.pprint()

	x = parse("(@nat.S @nat.O)")
	print x
	print x.infer(ctx)
	print x.normalize(ctx, EvalStrategy.CBV)

	print
	print "===== Matches"

	m = parse("match (@nat.S @nat.O) as x in x return nat with | @nat.O => @nat.O | (@nat.S y) => (@nat.S (@nat.S (f y))) end")
	print m
	print m.normalize(ctx, EvalStrategy.CBV)

	exit()

if __name__ == "__main__":
	ctx = Context()
	x = easy_parse.parse_term("((fun x : nat . ((fun j : nat . j) x)) y)")
	print x
	print x.normalize(ctx, EvalStrategy.WHNF)

	e1 = easy_parse.parse_term("(fun x : T . (fun x : Type0 . x))")
	e2 = easy_parse.parse_term("(fun z : J . (fun y : Type0 . y))")
	print e1
	print e2
	print alpha_equivalent(ctx, e1, e2)

#	print "=== Testing inference"
#	e = easy_parse.parse_term("(fun x : (forall y : Type0 . y) . (x x))")
#	print e
#	print e.infer(ctx)

