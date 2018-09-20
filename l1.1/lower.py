#!/usr/bin/python

import enum, argparse
import parsing
import inference
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
			# We set the declaration to have a hole type because all of our type information is already carried by the expr.
			# Once inference occurs the type inference will propagate up to this hole.
			type_annotation=core.PolyType(set(), core.HoleType()),
		)
		code_block.add(entry)

	def handle_letStatement(self, code_block, ast):
		code_block.add(core.Declaration(
			name=ast["name"],
			expr=self.lower_expr(ast["expr"]),
			type_annotation=core.PolyType(set(), self.optional_annot_to_type(ast["optionalTypeAnnot"])),
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
			code_block.add(core.ReturnStatement(self.lower_expr(expr)))
		else:
			code_block.add(core.ReturnStatement(core.VarExpr("nil")))

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
			arg_types.append(self.optional_annot_to_type(optional_arg_type))
		return_type = self.optional_annot_to_type(ast["returnType"])
		return arg_names, arg_types, return_type

	def lower_lambda_or_fn_ast(self, ast):
		func_expr = self.lower_expr(ast["result"])
		arg_names, arg_types, return_type = self.unpack_fn_types_helper(ast)
		return core.AbsExpr(
			arg_names,
			arg_types,
			func_expr,
			return_type,
		)

	def get_lambda_or_fn_type(self, ast):
		arg_names, arg_types, return_type = self.unpack_fn_types_helper(ast)
		if any(i is None for i in arg_types):
			raise ValueError("Cannot get explicit type of function without argument type annotations.")
		if return_type is None:
			raise ValueError("Cannot get explicit type of function without return type annotation.")
		return core.AppType("fun", arg_types + [return_type])

	def optional_annot_to_type(self, optional_annot):
		assert isinstance(optional_annot, list)
		if optional_annot:
			annot, = optional_annot
			return self.lower_type(annot)
		return core.HoleType()

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

	print utils.pretty(lowerer.top_level)

	print "=" * 20, "Doing inference."

	# Define a global typing context with an entry for nil.
	root_gamma = inference.Gamma()
	root_gamma[core.VarExpr("nil")] = core.PolyType(set(), core.AppType("nil", []))

	# Do inference.
	inf = inference.Inference()
	inf.infer_code_block(root_gamma, lowerer.top_level.root_block)

	print "=" * 20, "Inference complete."

	print utils.pretty(lowerer.top_level)

