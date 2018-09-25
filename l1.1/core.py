#!/usr/bin/python
# encoding: utf-8
"""
core.py

Contains data structures for reepresenting a desugared program in a "core" form.
The core form is designed to be relatively conducive to analysis, optimization, type checking, and trait resolution.
This core form is approximately analogous to rustc's MIR in that we desugar various looping constructs and whatnot, except that one lowers into the core language before type checking, unlike in rustc, where MIR is (necessarily) generated post-type checking and trait resolution.

A core translation unit consists of:

	A `TopLevel` which contains:
		an (ordered) dict `members` mapping names to either `DataType`s or `Trait`s.
		an (ordered) list `impls` of impls to test against for trait resolution.
		a single `CodeBlock` containing all of the other definitions and functions.
"""

import collections
import utils

class TopLevel:
	def __init__(self):
		self.members = collections.OrderedDict()
		self.impls = []
		self.root_block = CodeBlock()

	def __getitem__(self, name):
		return self.members[name]

	def __setitem__(self, name, value):
		if name in self.members:
			raise ValueError("Duplicate definition of: %s" % (name,))
		self.members[name] = value

	def add(self, entry):
		self.root_block.add(entry)

	def pretty(self, b):
		print >>b, "Top level definitions:"
		for member_name, member in self.members.iteritems():
			with b.indent():
				member.pretty(b)
		print >>b, "Impls:"
		for impl in self.impls:
			with b.indent():
				impl.pretty(b)
		print >>b, "Root block:"
		with b.indent():
			self.root_block.pretty(b)

# ===== Top level constructs (valid values in TopLevel.members)

class DataType:
	def __init__(self, name):
		self.name = name
		self.constructors = collections.OrderedDict()

	def __str__(self):
		return "dtype(%s)" % (self.name,)

	def pretty(self, b):
		print >>b, "Datatype: %s" % (self.name,)
		for constructor in self.constructors.itervalues():
			with b.indent():
				constructor.pretty(b)

	class DataConstructor:
		def __init__(self, parent, name, fields):
			assert isinstance(parent, DataType)
			# TODO: Maybe relax this into any MonoType?
#			assert all(isinstance(i, DataType) for i in fields)
			assert all(isinstance(i, MonoType) for i in fields)
			self.parent = parent
			self.name = name
			self.fields = fields

		def __str__(self):
			return "%s::%s" % (self.parent, self.name)

		def pretty(self, b):
			b.write("Constructor: %s(" % (self.name,))
			for i, field in enumerate(self.fields):
				with b.indent():
					field.pretty(b)
				if i != len(self.fields) - 1:
					b.write(", ")
			b.write(")\n")
#			print >>b, "Constructor: %s(%s)" % (
#				self.name,
#				", ".join(map(str, self.fields)),
#			)

class Trait:
	def __init__(self, name):
		self.name = name
		self.code_block = CodeBlock()

	def pretty(self, b):
		b.write("Trait: %s " % (self.name,))
		with b.indent():
			self.code_block.pretty(b)
		b.write("\n")

# ===== Impls

class Impl:
	def __init__(self, trait_expr, type_expr):
		assert isinstance(trait_expr, MonoType) # XXX: Later maybe this is separate?
		assert isinstance(type_expr, MonoType)
		self.trait_expr = trait_expr
		self.type_expr = type_expr
		self.code_block = CodeBlock()

	def pretty(self, b):
		b.write("Impl: ")
		with b.indent():
			self.trait_expr.pretty(b)
		b.write(" for ")
		with b.indent():
			self.type_expr.pretty(b)
		b.write(" ")
		with b.indent():
			self.code_block.pretty(b)
		b.write("\n")

# ===== Imperative (CodeBlock-related) constructs

class CodeBlock:
	def __init__(self):
		self.entries = []
		self.return_monotype = None

	def pretty(self, b):
		b.write("{\n")
		with b.indent():
			for entry in self.entries:
				entry.pretty(b)
		b.write("}")

	def add(self, entry):
		assert isinstance(entry, CodeBlock.Entry)
		self.entries.append(entry)

	def name_deps(self):
		# Although CodeBlocks aren't valid a CodeBlock.Entry, we still
		# define name_deps for when we're nested inside a BlockExpr.
		names = set()
		for entry in self.entries:
			names |= entry.name_deps()
		for entry in self.entries:
			names -= entry.provided_names()
		return names

	class Entry:
		def provided_names(self):
			return set()

		def name_deps(self):
			return set()

class Stub(CodeBlock.Entry):
	def __init__(self, name, type_expr):
		assert isinstance(name, str)
		assert isinstance(type_expr, MonoType)
		self.name = name
		self.type_expr = type_expr

	def pretty(self, b):
		b.write("stub %s : " % (self.name,))
		self.type_expr.pretty(b)
		b.write("\n")

	def provided_names(self):
		return set([self.name])

	def name_deps(self):
		return self.type_expr.name_deps()

class Declaration(CodeBlock.Entry):
	def __init__(self, name, expr, type_annotation):
		assert isinstance(name, str)
		assert isinstance(expr, Expr)
		assert isinstance(type_annotation, PolyType)
		self.name = name
		self.expr = expr
		self.type_annotation = type_annotation

	def __repr__(self):
		return "<Declaration %s>" % (self.name,)

	def pretty(self, b):
		b.write(self.name)
#		if not isinstance(self.type_annotation, HoleType):
		if True:
			b.write(" : ")
			self.type_annotation.pretty(b)
		b.write(" := ")
		self.expr.pretty(b)
		b.write("\n")

	def provided_names(self):
		return set([self.name])

	def name_deps(self):
		return self.expr.name_deps()

class Reassignment(CodeBlock.Entry):
	def __init__(self, name, expr):
		self.name = name
		self.expr = expr

	def pretty(self, b):
		b.write("%s = " % (self.name,))
		with b.indent():
			self.expr.pretty(b)
		b.write("\n")

	# Doesn't provide any names, because we just redefine one.
#	def provided_names(self):
#		return set([self.name])

class TypeConstraint(CodeBlock.Entry):
	def __init__(self, expr, type_expr):
		assert isinstance(expr, Expr)
		assert isinstance(type_expr, MonoType)
		self.expr = expr
		self.type_expr = type_expr

	def pretty(self, b):
		b.write("typecheck ")
		with b.indent():
			self.expr.pretty(b)
			b.write(" : ")
			self.type_expr.pretty(b)
		b.write("\n")
#		print >>b, "typecheck %s : %s" % (self.expr, self.type_expr)

class ExprEvaluation(CodeBlock.Entry):
	def __init__(self, expr):
		assert isinstance(expr, Expr)
		self.expr = expr

	def pretty(self, b):
		b.write("eval ")
		self.expr.pretty(b)
		b.write("\n")

class LoopStatement(CodeBlock.Entry):
	def __init__(self, code_block):
		self.code_block = code_block

	def pretty(self, b):
		b.write("loop ")
		with b.indent():
			self.code_block.pretty(b)

	def name_deps(self):
		return self.code_block.name_deps()

class ReturnStatement(CodeBlock.Entry):
	def __init__(self, expr):
		self.expr = expr

	def pretty(self, b):
		b.write("return ")
		self.expr.pretty(b)
		b.write("\n")

	def name_deps(self):
		return self.expr.name_deps()

# ===== Core expression language.

class Expr(utils.HashableMixin):
	# XXX: This is a little bad, because I maybe want to keep things more explicit.
	def __repr__(self):
		return str(utils.pretty(self))

class LiteralExpr(Expr):
	def __init__(self, literal):
		assert isinstance(literal, (int, float, str))
		self.literal = literal

	def key(self):
		return self.literal

	def pretty(self, b):
		b.write("lit(%r)" % (self.literal,))

	def name_deps(self):
		return set()

class BlockExpr(Expr):
	def __init__(self, code_block):
		self.code_block = code_block

	def key(self):
		raise NotImplementedError("Hashability isn't yet implemented for BlockExpr.")

	def pretty(self, b):
		self.code_block.pretty(b)

	def name_deps(self):
		return self.code_block.name_deps()

class VarExpr(Expr):
	def __init__(self, name):
		self.name = name

	def key(self):
		return self.name

	def pretty(self, b):
		b.write("%%%s" % (self.name,))

	def name_deps(self):
		return set([self.name])

class AppExpr(Expr):
	def __init__(self, fn_expr, arg_exprs):
		self.fn_expr = fn_expr
		self.arg_exprs = arg_exprs

	def key(self):
		return self.fn_expr, tuple(self.arg_exprs)

	def pretty(self, b):
		self.fn_expr.pretty(b)
		b.write("(")
		for i, arg_expr in enumerate(self.arg_exprs):
			arg_expr.pretty(b)
			if i != len(self.arg_exprs) - 1:
				b.write(", ")
		b.write(")")

	def name_deps(self):
		v = self.fn_expr.name_deps()
		for arg in self.arg_exprs:
			v |= arg.name_deps()
		return v

# This is hopefully temporary.
# I hope to one day switch this over to a "trait resolution" node.
# The idea is that we would lower x.foo(y) into some sort of:
#   trait_resolve(x, "foo")(x, y)
class MethodCallExpr(Expr):
	def __init__(self, fn_expr, method_name, arg_exprs):
		self.fn_expr = fn_expr
		self.method_name = method_name
		self.arg_exprs = arg_exprs

	def key(self):
		return self.fn_expr, self.method_name, tuple(self.arg_exprs)

	def pretty(self, b):
		self.fn_expr.pretty(b)
		b.write("::%s" % (self.method_name,))
		b.write("(")
		for i, arg_expr in enumerate(self.arg_exprs):
			arg_expr.pretty(b)
			if i != len(self.arg_exprs) - 1:
				b.write(", ")
		b.write(")")

	def name_deps(self):
		v = self.fn_expr.name_deps()
		for arg in self.arg_exprs:
			v |= arg.name_deps()
		return v

class AbsExpr(Expr):
	def __init__(self, arg_names, arg_types, result_expr, return_type):
		assert all(isinstance(i, MonoType) for i in arg_types)
		assert len(arg_names) == len(arg_types)
		assert isinstance(result_expr, Expr)
		assert isinstance(return_type, MonoType)
		self.arg_names = arg_names
		self.arg_types = arg_types
		self.result_expr = result_expr
		self.return_type = return_type

	def key(self):
		return tuple(self.arg_names), tuple(self.arg_types), self.result_expr, self.return_type

	def pretty(self, b):
		b.write("\\")
		for i, (arg_name, arg_type) in enumerate(zip(self.arg_names, self.arg_types)):
			b.write(arg_name)
			if not isinstance(arg_type, HoleType):
				b.write(" : ")
				with b.indent():
					arg_type.pretty(b)
			if i != len(self.arg_names) - 1:
				b.write(", ")
		b.write(" -> ")
		with b.indent():
			self.result_expr.pretty(b)
		if not isinstance(self.return_type, HoleType):
			b.write(" : ")
			self.return_type.pretty(b)

	def name_deps(self):
		return self.result_expr.name_deps() - set(self.arg_names)

class LetExpr(Expr):
	def __init__(self, name, expr1, expr2):
		self.name = name
		self.expr1 = expr1
		self.expr2 = expr2

	def key(self):
		return self.name, self.expr1, self.expr2

	def pretty(self, b):
		b.write("let %s := " % (self.name,))
		with b.indent():
			self.expr1.pretty(b)
		b.write(" in\n")
		self.expr2.pretty(b)

	def name_deps(self):
		return self.expr1.name_deps() | (self.expr2.name_deps() - set([self.name]))

class IfExpr(Expr):
	def __init__(self, cond_expr, true_expr, false_expr):
		self.cond_expr = cond_expr
		self.true_expr = true_expr
		self.false_expr = false_expr

	def key(self):
		return self.cond_expr, self.true_expr, self.false_expr

	def pretty(self, b):
		b.write("if ")
		with b.indent():
			self.cond_expr.pretty(b)
		b.write(" then ")
		with b.indent():
			self.true_expr.pretty(b)
		b.write(" else ")
		with b.indent():
			self.false_expr.pretty(b)

	def name_deps(self):
		return self.cond_expr.name_deps() | self.true_expr.name_deps() | self.false_expr.name_deps()

# ===== Core type expression language.

class MonoType(utils.HashableMixin):
	# XXX: This is a little bad, because I maybe want to keep things more explicit.
	def __repr__(self):
		return str(utils.pretty(self))

class HoleType(MonoType):
	def key(self):
		pass

	def pretty(self, b):
		b.write("_")

	def free_type_variables(self):
		return set()

	def apply_type_subs(self, type_subs):
		return self

class AppType(MonoType):
	def __init__(self, constructor, args):
#		assert isinstance(constructor, DataType.DataConstructor)
		assert isinstance(constructor, str)
		assert all(isinstance(i, MonoType) for i in args)
		self.constructor = constructor
		self.args = args

	def key(self):
		return self.constructor, tuple(self.args)

	def pretty(self, b):
#		b.write(self.constructor.name)
		b.write(self.constructor)
		if self.args:
			b.write("<")
			with b.indent():
				for i, arg in enumerate(self.args):
					arg.pretty(b)
					if i != len(self.args) - 1:
						b.write(", ")
			b.write(">")

	def free_type_variables(self):
		v = set()
		for arg in self.args:
			v |= arg.free_type_variables()
		return v

	def apply_type_subs(self, type_subs):
		if self in type_subs:
			return type_subs[self]
		return AppType(
			self.constructor,
			[arg.apply_type_subs(type_subs) for arg in self.args],
		)

class VarType(MonoType):
	def __init__(self, name):
		assert isinstance(name, str)
		self.name = name

	def key(self):
		return self.name

	def pretty(self, b):
		b.write("?%s" % (self.name,))

	def free_type_variables(self):
		return set([self])

	def apply_type_subs(self, type_subs):
		if self in type_subs:
			return type_subs[self]
		return self

class PolyType(utils.HashableMixin):
	def __init__(self, binders, mono):
		assert isinstance(binders, set)
		assert all(isinstance(binder, VarType) for binder in binders)
		assert isinstance(mono, MonoType)
		self.binders = binders
		self.mono = mono

	def __repr__(self):
		return str(utils.pretty(self))

	def key(self):
		return frozenset(self.binders), self.mono

	def pretty(self, b):
		b.write("∀")
		if self.binders:
			for binder in sorted(self.binders):
				b.write(" ")
				binder.pretty(b)
		b.write(", ")
		self.mono.pretty(b)

	def free_type_variables(self):
		return self.mono.free_type_variables() - self.binders

	def is_concrete(self):
		# We're concrete if our monotype has no free type variables, bound or not.
		return self.mono.free_type_variables() == set()

if __name__ == "__main__":
	tl = TopLevel()
	Nat = tl["Nat"] = DataType("Nat")
	Nat.constructors["Z"] = DataType.DataConstructor(Nat, "Z", [])
	Nat.constructors["S"] = DataType.DataConstructor(Nat, "S", [AppType("Nat", [])])

	id_func = AbsExpr(["x"], [HoleType()], VarExpr("x"), HoleType())
	tl.root_block.add(Declaration("id", id_func, HoleType()))

	main_block = CodeBlock()
	main_block.add(Declaration("id", id_func, HoleType()))
	main_expr = BlockExpr(main_block)
	main_func = AbsExpr(["x"], [HoleType()], main_expr, HoleType())
	tl.root_block.add(Declaration("main", main_func, HoleType()))

	b = utils.StringBuilder()
	tl.pretty(b)
	print b

