#!/usr/bin/python

import sys
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
	def __init__(self):
		self.typings = {}
		self.definitions = {}
		self.inductives = {}

	def copy(self):
		new_ctx = Context()
		new_ctx.typings = self.typings.copy()
		new_ctx.definitions = self.definitions.copy()
		new_ctx.inductives = self.inductives.copy()
		return new_ctx

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

	def extend_ty(self, var, ty):
		assert isinstance(var, Var)
		assert var not in self.definitions
		ctx = self.copy()
		ctx.typings[var] = ty
		return ctx

	def extend_def(self, var, term):
		assert isinstance(var, Var)
		assert var not in self.typings
		ctx = self.copy()
		ctx.definitions[var] = term
		return ctx

class Parameters:
	def __init__(self, names, types):
		assert len(names) == len(types)
		assert all(isinstance(name, str) for name in names)
		assert all(isinstance(ty, Term) for ty in types)
		self.names = names
		self.types = types

	def __repr__(self):
		return " ".join(
			"(%s : %s)" % (name, ty)
			for name, ty in zip(self.names, self.types)
		)

class Inductive:
	class Constructor:
		def __init__(self, ty):
			assert isinstance(ty, Term)
			self.ty = ty

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

	def check_arity(self, arity):
		# A sort is always a valid arity.
		if arity.is_sort():
			return
		assert isinstance(arity, DepProd), "Arities must be a product terminating with a sort."
		self.check_arity(arity.result_ty)

	def add_constructor(self, con_name, ty):
		self.constructors[con_name] = Inductive.Constructor(ty)
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
	def subst(self, x, y): raise NotImplementedError
	def normalize(self, ctx, strategy): raise NotImplementedError
	def infer(self, ctx): raise NotImplementedError
	def free_vars(self): raise NotImplementedError
	# If you're implementing a subclass also add handling to AlphaCanonicalizer.

	def check(self, ctx, ty):
		inferred_type = self.infer(ctx)
		if not compare_terms(ctx, inferred_type, ty):
			raise TypeCheckFailure("Failure to match: %r != %r" % (inferred_type, ty))

	def is_sort(self):
		return False

class Annot(Term):
	def __init__(self, term, ty):
		self.term = term
		self.ty = ty

	def key(self):
		return self.term, self.ty

	def __repr__(self):
		return "%s :: %s" % (self.term, self.ty)

	def subst(self, x, y):
		return Annot(self.term.subst(x, y), self.ty.subst(x, y))

	def normalize(self, ctx, strategy):
		return Annot(
			self.term.normalize(ctx, strategy),
			self.ty.normalize(ctx, strategy),
		)

	def infer(self, ctx):
		# XXX: This might not be right.
		self.ty.check(ctx, SortType())
		self.term.check(ctx, self.ty), "Type annotation failed!"
		return self.ty

	def free_vars(self, ctx):
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

	def subst(self, x, y):
		return self

	def normalize(self, ctx, strategy):
		return self

	def infer(self, ctx):
		return SortType(self.universe_index + 1)

	def check(self, ctx, ty):
		if ty != self:
			raise TypeCheckFailure("Failure to match: %r != %r" % (ty, self))

	def free_vars(self):
		return set()

	def is_sort(self):
		return True

class SortProp(SortType):
	def __repr__(self):
		return "\xe2\x84\x99"

	def infer(self, ctx):
		# Implement Prop : Type
		return SortType()

class Var(Term):
	def __init__(self, var):
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
			return ctx.lookup_def(self)
		# XXX: This should be an error!
		# We need a separate atom type soon.
		return self

	def infer(self, ctx):
		return ctx.lookup_ty(self)

	def free_vars(self):
		return set([self])

class DepProd(Term):
	def __init__(self, var, var_ty, result_ty):
		assert isinstance(var, Var)
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
		return DepProd(
			self.var,
			self.var_ty.subst(x, y),
			self.result_ty.subst(x, y),
		)

	def normalize(self, ctx, strategy):
		return self
#		return DepProd(self.var, self.var_ty.normalize(ctx, strategy), self.res_ty.normalize(ctx, strategy))

	def infer(self, ctx):
		# Check all the types.
		self.var_ty.check(ctx, SortType())
		return SortType()

	def check(self, ctx, ty):
		return self.infer(ctx) == ty

	def free_vars(self):
		return self.var_ty.free_vars() | (self.result_ty.free_vars() - set([self.var]))

class Abs(Term):
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
		assert x != self.var
		return Abs(
			self.var,
			self.var_ty.subst(x, y),
			self.result.subst(x, y),
		)

	def normalize(self, ctx, strategy):
		return self
#		return Abs(self.var, self.var_ty.normalize(ctx, strategy), self.result.normalize(ctx, strategy))

	def infer(self, ctx):
		self.var_ty.check(ctx, SortType())
		ctx = ctx.extend_ty(self.var, self.var_ty)
		u = self.result.infer(ctx)
		# XXX: Do I need to abstract over self.var somehow?
		return DepProd(self.var, self.var_ty, u)

	def free_vars(self):
		return self.var_ty.free_vars() | (self.result.free_vars() - set([self.var]))

class App(Term):
	def __init__(self, fn, arg):
		self.fn = fn
		self.arg = arg

	def key(self):
		return self.fn, self.arg

	def __repr__(self):
		return "(%s %s)" % (self.fn, self.arg)

	def subst(self, x, y):
		return App(self.fn.subst(x, y), self.arg.subst(x, y))

	def normalize(self, ctx, strategy):
		fn = self.fn.normalize(ctx, strategy)
		arg = self.arg
		if strategy == EvalStrategy.CBV:
			arg = arg.normalize(ctx, strategy)
		# If our function isn't concrete, then early out.
		if not isinstance(fn, Abs):
			return App(fn, arg)
		# Perform a substitution.
		instantiation = fn.result.subst(fn.var, arg)
		return instantiation.normalize(ctx, strategy)

	def infer(self, ctx):
		fn_type = self.fn.infer(ctx)
		fn_type = coerce_to_product(ctx, fn_type)
		self.arg.check(ctx, fn_type.var_ty)
		return fn_type.result_ty.subst(fn_type.var, self.arg)

	def free_vars(self):
		return self.fn.free_vars() | self.arg.free_vars()

class InductiveConstructor(Term):
	def __init__(self, name, con_name):
		self.name = name
		self.con_name = con_name

	def key(self):
		return self.name, self.con_name

	def __repr__(self):
		return "@%s.%s" % (self.name, self.con_name)

	def subst(self, x, y):
		return self

	def normalize(self, ctx, strategy):
		return self

	def infer(self, ctx):
		return ctx.inductives[self.name].constructors[self.con_name].ty

	def free_vars(self, ctx):
		return set()

class Match(Term):
	class Arm(HashableMixin):
		def __init__(self, pattern, result):
			self.pattern = pattern
			self.result = result

		def key(self):
			return self.pattern, self.result

		def __repr__(self):
			return "| %s => %s" % (self.pattern, self.result)

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
		# We have to be careful again about captures because
		assert False

	def normalize(self, ctx, strategy):
		# Here's where we do complicated stuff!
		pass

# ===== End term ilks =====

def compare_terms(ctx, t1, t2):
	t1 = t1.normalize(ctx, EvalStrategy.CBV)
	t2 = t2.normalize(ctx, EvalStrategy.CBV)
	# TODO: Maybe implement the additional rules that Spartan TT does?
	return alpha_equivalent(t1, t2)

def coerce_to_product(ctx, term):
	assert isinstance(term, Term)
	term = term.normalize(ctx, EvalStrategy.WHNF)
	assert isinstance(term, DepProd), "Bad product: %r" % (term,)
	return term

class AlphaCanonicalizer:
	def __init__(self):
		self.subs = {}
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
		elif isinstance(t, Annot):
			return Annot(
				self.canonicalize(t.term),
				self.canonicalize(t.ty),
			)
		elif isinstance(t, SortType):
			return t
		elif isinstance(t, (DepProd, Abs)):
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
			if isinstance(t, DepProd):
				return DepProd(
					self.canonicalize(t.var),
					self.canonicalize(t.var_ty),
					self.canonicalize(t.result_ty),
				)
			else:
				return Abs(
					self.canonicalize(t.var),
					self.canonicalize(t.var_ty),
					self.canonicalize(t.result),
				)
			if saved_subs != None:
				self.subs = saved_subs
		elif isinstance(t, App):
			return App(
				self.canonicalize(t.fn),
				self.canonicalize(t.arg),
			)
		raise NotImplementedError("Unhandled: %r" % (t,))

def alpha_canonicalize(term):
	canonicalizer = AlphaCanonicalizer()
	return canonicalizer.canonicalize(term)

def alpha_equivalent(t1, t2):
	return alpha_canonicalize(t1) == alpha_canonicalize(t2)

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

	m = parse("match (@nat.S @nat.O) as x in x return nat with | foo => bar | (foo _)  => biz end")
	print m

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
	print alpha_equivalent(e1, e2)

#	print "=== Testing inference"
#	e = easy_parse.parse_term("(fun x : (forall y : Type0 . y) . (x x))")
#	print e
#	print e.infer(ctx)

