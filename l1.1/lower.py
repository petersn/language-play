#!/usr/bin/python

import enum, argparse
import parsing
import inference
import traits
import core
import utils

def extract_qual_name(qualName):
	assert qualName.name == "qualName"
	name, = qualName.contents
	return name

def not_handled(defin):
	raise NotImplementedError("unhandled definition: %r" % (defin,))

class Lowerer:
	def __init__(self):
		self.top_level = core.TopLevel()

	def add_code_block(self, code_block, ast):
		assert ast.name == "codeBlock"
		for ast in ast["statements"]:
			getattr(self, "handle_" + ast.name)(code_block, ast)

	def handle_dataDeclaration(self, code_block, ast):
		datatype = core.DataType(ast["name"])
		for con_ast in ast["constructors"]:
			con_name = con_ast["name"]
			fields = [self.lower_type(field) for field in con_ast["fields"]]
			con_entry = core.DataType.DataConstructor(datatype, con_name, fields)
			datatype.constructors[con_name] = con_entry
		self.top_level[ast["name"]] = datatype

	def handle_traitDeclaration(self, code_block, ast):
		trait = core.Trait(ast["name"])
		self.add_code_block(trait.code_block, ast["body"])
		self.top_level[ast["name"]] = trait

	def handle_implDeclaration(self, code_block, ast):
		trait_expr = self.lower_type(ast["trait"])
		type_expr = self.lower_type(ast["forType"])
		impl = core.Impl(trait_expr, type_expr)
		self.add_code_block(impl.code_block, ast["body"])
		self.top_level.impls.append(impl)

	def handle_fnStub(self, code_block, ast):
		fn_type = self.get_lambda_or_fn_type(ast)
		code_block.add(core.Stub(ast["name"], fn_type))

	def handle_parameterStub(self, code_block, ast):
		type_expr = self.lower_type(ast["typeAnnot"])
		code_block.add(core.Stub(ast["name"], type_expr))

	def handle_fnDeclaration(self, code_block, ast):
		entry = core.Declaration(
			name=ast["name"],
			expr=self.lower_lambda_or_fn_ast(ast),
		)
		code_block.add(entry)

	def handle_letStatement(self, code_block, ast):
		type_annotation = None
		if ast["optionalTypeAnnot"]:
			x, = ast["optionalTypeAnnot"]
			type_annotation = self.lower_type(x)
		code_block.add(core.Declaration(
			name=ast["name"],
			expr=self.lower_expr(ast["expr"]),
			type_annotation=type_annotation,
		))

	def handle_reassignmentStatement(self, code_block, ast):
		self.handle_letStatement(code_block, ast)

	def handle_ifStatement(self, code_block, ast):
		cond_expr = self.lower_expr(ast["condExpr"])
		true_expr = self.lower_expr(ast["body"])
		false_expr = core.VarExpr("nil")
		if_expr = core.IfExpr(cond_expr, true_expr, false_expr)
		code_block.add(core.ExprEvaluation(if_expr))

	def handle_exprStatement(self, code_block, ast):
		code_block.add(core.ExprEvaluation(self.lower_expr(ast["expr"])))

	def handle_returnStatement(self, code_block, ast):
		if ast["optionalExpr"]:
			expr, = ast["optionalExpr"]
			return core.ReturnExpr(self.lower_expr(expr))
		else:
			return core.ReturnExpr(core.VarExpr("nil"))

	def handle_query(self, code_block, ast):
		print "Query:", ast

	def lower_expr(self, ast):
		if ast.name == "codeBlock":
			block = core.CodeBlock()
			self.add_code_block(block, ast)
			return core.BlockExpr(block)
		elif ast.name == "appExpr":
			return core.AppExpr(
				self.lower_expr(ast["fn"]),
				[
					self.lower_expr(arg)
					for arg in ast["args"]
				],
			)
		elif ast.name == "qualName":
			return core.VarExpr(extract_qual_name(ast))
		elif ast.name == "lambdaExpr":
			return self.lower_lambda_or_fn_ast(ast)
		raise NotImplementedError("Not handled expr: %r" % (ast,))

	def unpack_fn_types_helper(self, ast):
		arg_names = []
		arg_types = []
		for arg_name, optional_arg_type in ast["args"]:
			arg_names.append(arg_name)
			if optional_arg_type:
				x, = optional_arg_type
				arg_types.append(self.lower_type(x))
			else:
				arg_types.append(None)
		return_type = None
		if ast["returnType"]:
			x, = ast["returnType"]
			return_type = self.lower_type(x)
		return arg_names, arg_types, return_type

	def lower_lambda_or_fn_ast(self, ast):
		func_expr = self.lower_expr(ast["result"])
		arg_names, arg_types, return_type = self.unpack_fn_types_helper(ast)
		return core.AbsExpr(
			arg_names,
			arg_types,
			func_expr,
			return_type=return_type,
		)

	def get_lambda_or_fn_type(self, ast):
		arg_names, arg_types, return_type = self.unpack_fn_types_helper(ast)
		if any(i is None for i in arg_types):
			raise ValueError("Cannot get explicit type of function without argument type annotations.")
		if return_type is None:
			raise ValueError("Cannot get explicit type of function without return type annotation.")
		return core.AppType("fun", arg_types + [return_type])

	def lower_type(self, ast):
		if ast.name == "qualName":
			return core.AppType(
				constructor=extract_qual_name(ast),
				args=[],
			)
		elif ast.name == "typeGeneric":
			return core.AppType(
				constructor=extract_qual_name(ast["generic"]),
				args=[self.lower_type(arg) for arg in ast["args"]],
			)
		raise NotImplementedError("Not handled type: %r" % (ast,))

if __name__ == "__main__":
	p = argparse.ArgumentParser()
	p.add_argument("source")
	args = p.parse_args()

	with open(args.source) as f:
		source = f.read()

	ast = parsing.parse(source)

	lowerer = Lowerer()
	lowerer.add_code_block(lowerer.top_level.root_block, ast)

	b = utils.StringBuilder()
	lowerer.top_level.pretty(b)
	print b

