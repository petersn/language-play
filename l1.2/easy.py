#!/usr/bin/python

import sys
sys.modules["easy"] = sys.modules["__main__"]

import enum
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

	def copy(self):
		new_ctx = Context()
		new_ctx.typings = self.typings.copy()
		new_ctx.definitions = self.definitions.copy()
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
		self.ty.check(ctx, RootType())
		self.term.check(ctx, self.ty), "Type annotation failed!"
		return self.ty

	def free_vars(self, ctx):
		# XXX: Should the annotation be included in free variables?
		# Hmm...
		return self.term.free_vars() | self.ty.free_vars()

class RootType(Term):
	def key(self):
		return

	def __repr__(self):
		return "\xf0\x9d\x95\x8b"

	def subst(self, x, y):
		return self

	def normalize(self, ctx, strategy):
		return self

	def infer(self, ctx):
		# XXX: Girard's paradox.
		return self

	def check(self, ctx, ty):
		if ty != self:
			raise TypeCheckFailure("Failure to match: %r != %r" % (ty, self))

	def free_vars(self):
		return set()

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
		self.var_ty.check(ctx, RootType())
		return RootType()

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
		self.var_ty.check(ctx, RootType())
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
		elif isinstance(t, RootType):
			return t
		elif isinstance(t, (DepProd, Abs)):
			# There is a subtle case here.
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

if __name__ == "__main__":
	ctx = Context()
	x = easy_parse.parse_term("((fun x : nat . ((fun j : nat . j) x)) y)")
	print x
	print x.normalize(ctx, EvalStrategy.WHNF)

	e1 = easy_parse.parse_term("(fun x : T . (fun x : Type . x))")
	e2 = easy_parse.parse_term("(fun z : J . (fun y : Type . y))")
	print e1
	print e2
	print alpha_equivalent(e1, e2)

	print "=== Testing inference"
	e = easy_parse.parse_term("(fun x : (forall y : Type . y) . (x z))")
	print e
	print e.infer(ctx)

