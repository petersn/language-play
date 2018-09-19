#!/usr/bin/python
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
			# TODO: Maybe relax this into any TypeExpr?
#			assert all(isinstance(i, DataType) for i in fields)
			assert all(isinstance(i, TypeExpr) for i in fields)
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
		assert isinstance(trait_expr, TypeExpr) # XXX: Later maybe this is separate?
		assert isinstance(type_expr, TypeExpr)
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

	def add(self, entry):
		self.entries.append(entry)

	def pretty(self, b):
		b.write("{\n")
		with b.indent():
			for entry in self.entries:
				entry.pretty(b)
		b.write("}")

class Stub:
	def __init__(self, name, type_expr):
		assert isinstance(name, str)
		assert isinstance(type_expr, TypeExpr)
		self.name = name
		self.type_expr = type_expr

	def pretty(self, b):
		b.write("stub %s : " % (self.name,))
		self.type_expr.pretty(b)
		b.write("\n")

class Declaration:
	def __init__(self, name, expr, type_annotation=None):
		assert isinstance(name, str)
		assert isinstance(expr, Expr)
		assert type_annotation is None or isinstance(type_annotation, TypeExpr)
		self.name = name
		self.expr = expr
		self.type_annotation = type_annotation

	def pretty(self, b):
		b.write(self.name)
		if self.type_annotation != None:
			b.write(" : ")
			self.type_annotation.pretty(b)
		b.write(" := ")
		self.expr.pretty(b)
		b.write("\n")

class Reassignment:
	def __init__(self, name, expr):
		self.name = name
		self.expr = expr

	def pretty(self, b):
		b.write("%s = " % (self.name,))
		with b.indent():
			self.expr.pretty(b)
		b.write("\n")

class TypeConstraint:
	def __init__(self, expr, type_expr):
		assert isinstance(expr, Expr)
		assert isinstance(type_expr, TypeExpr)
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

class ExprEvaluation:
	def __init__(self, expr):
		assert isinstance(expr, Expr)
		self.expr = expr

	def pretty(self, b):
		b.write("eval ")
		self.expr.pretty(b)
		b.write("\n")

# ===== Core expression language.

class Expr:
	pass

class BlockExpr(Expr):
	def __init__(self, code_block):
		self.code_block = code_block

	def pretty(self, b):
		self.code_block.pretty(b)

class VarExpr(Expr):
	def __init__(self, name):
		self.name = name

	def pretty(self, b):
		b.write("%%%s" % (self.name,))

class AppExpr(Expr):
	def __init__(self, fn_expr, arg_exprs):
		self.fn_expr = fn_expr
		self.arg_exprs = arg_exprs

	def pretty(self, b):
		self.fn_expr.pretty(b)
		b.write("(")
		for i, arg_expr in enumerate(self.arg_exprs):
			arg_expr.pretty(b)
			if i != len(self.arg_exprs) - 1:
				b.write(", ")
		b.write(")")

class AbsExpr(Expr):
	def __init__(self, arg_names, arg_types, expr, return_type=None):
		assert isinstance(expr, Expr)
		assert all(i is None or isinstance(i, TypeExpr) for i in arg_types)
		assert len(arg_names) == len(arg_types)
		assert return_type is None or isinstance(return_type, TypeExpr)
		self.arg_names = arg_names
		self.arg_types = arg_types
		self.expr = expr
		self.return_type = return_type

	def pretty(self, b):
		b.write("\\")
		for i, (arg_name, arg_type) in enumerate(zip(self.arg_names, self.arg_types)):
			b.write(arg_name)
			if arg_type != None:
				b.write(" : ")
				with b.indent():
					arg_type.pretty(b)
			if i != len(self.arg_names) - 1:
				b.write(", ")
		b.write(" -> ")
#		b.write("\\%s -> " % (
#			", ".join(arg_name for arg_name in self.arg_names),
#		))
		with b.indent():
			self.expr.pretty(b)
		if self.return_type != None:
			b.write(" : ")
			self.return_type.pretty(b)

#	def __str__(self):
#		return "\%s -> %s" % (
#			", ".join(arg_name for arg_name in self.arg_names),
#			self.expr,
#		)

class LetExpr(Expr):
	def __init__(self, name, expr1, expr2):
		self.name = name
		self.expr1 = expr1
		self.expr2 = expr2

	def pretty(self, b):
		b.write("let %s := " % (self.name,))
		with b.indent():
			self.expr1.pretty(b)
		b.write(" in\n")
		self.expr2.pretty(b)

class IfExpr(Expr):
	def __init__(self, cond_expr, true_expr, false_expr):
		self.cond_expr = cond_expr
		self.true_expr = true_expr
		self.false_expr = false_expr

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

#	def __str__(self):
#		return "if %s then %s else %s" % (self.cond_expr, self.true_expr, self.false_expr)

class LoopExpr(Expr):
	def __init__(self, expr):
		self.expr = expr

	def pretty(self, b):
		b.write("loop ")
		self.expr.pretty(b)

class ReturnExpr(Expr):
	def __init__(self, expr):
		self.expr = expr

	def pretty(self, b):
		b.write("return ")
		self.expr.pretty(b)
		b.write("\n")

# ===== Core type expression language.

class TypeExpr:
	pass

class AppType(TypeExpr):
	def __init__(self, constructor, args):
#		assert isinstance(constructor, DataType.DataConstructor)
		assert isinstance(constructor, str)
		assert all(isinstance(i, TypeExpr) for i in args)
		self.constructor = constructor
		self.args = args

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

if __name__ == "__main__":
	tl = TopLevel()
	Nat = tl["Nat"] = DataType("Nat")
	Nat.constructors["Z"] = DataType.DataConstructor(Nat, "Z", [])
	Nat.constructors["S"] = DataType.DataConstructor(Nat, "S", [AppType("Nat", [])])

	id_func = AbsExpr(["x"], [None], VarExpr("x"))
	tl.root_block.add(Declaration("id", id_func))

	main_block = CodeBlock()
	main_block.add(Declaration("id", id_func))
	main_expr = BlockExpr(main_block)
	main_func = AbsExpr(["x"], [None], main_expr)
	tl.root_block.add(Declaration("main", main_func))

	b = utils.StringBuilder()
	tl.pretty(b)
	print b

