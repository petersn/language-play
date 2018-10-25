#!/usr/bin/python

import easy_parse

class HashableMixin:
	def __eq__(self, other):
		return self.__class__ is other.__class__ and self.key() == other.key()

	def __hash__(self):
		return hash(self.key())

class Term(HashableMixin):
	pass

class Annot(Term):
	def __init__(self, term, ty):
		self.term = term
		self.ty = ty

	def key(self):
		return self.term, self.ty

	def __repr__(self):
		return "%s :: %s" % (self.term, self.ty)

	def normalize(self):
		return self.term.normalize()

	def infer(self, ctx):
		pass

	def check(self, ctx, ty):
		pass

class RootType(Term):
	def key(self):
		return

	def __repr__(self):
		return "\xf0\x9d\x95\x8b"

	def normalize(self):
		return self

	def infer(self, ctx):
		return self, self

	def check(self, ctx, ty):
		assert ty == self

class Var(Term):
	def __init__(self, var):
		self.var = var

	def key(self):
		return self.var

	def __repr__(self):
		return self.var

	def normalize(self):
		return self

	def infer(self, ctx):
		return ctx[self]

class DepProd(Term):
	def __init__(self, var, var_ty, result_ty):
		assert isinstance(var, Var)
		self.var = var
		self.var_ty = var_ty
		self.result_ty = result_ty

	def key(self):
		return self.var, self.var_ty, self.result_ty

	def __repr__(self):
		return "(\xe2\x88\x80 %s : %s . %s)" % (self.var, self.var_ty, self.result_ty)

	def normalize(self):
		return DepProd(self.var, self.var_ty.normalize(), self.res_ty.normalize())

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

	def normalize(self):
		return Abs(self.var, self.var_ty.normalize(), self.result.normalize())

class App(Term):
	def __init__(self, fn, arg):
		self.fn = fn
		self.arg = arg

	def key(self):
		return self.fn, self.arg

	def __repr__(self):
		return "(%s %s)" % (self.fn, self.arg)

	def normalize(self):
		fn = self.fn.normalize()
		arg = self.arg.normalize()
		# If our function isn't concrete, then early out.
		if not isinstance(fn, Abs):
			return App(fn, arg)
		# Perform a substitution.
		result = fn.subst(fn.arg, arg)
		# I think no additional normalization is required here!
		assert result == result.normalize()

if __name__ == "__main__":
	x = easy_parse.parse_term("(fun x : nat . (x x))")
	print x

