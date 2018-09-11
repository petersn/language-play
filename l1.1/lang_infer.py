#!/usr/bin/python

import argparse
import parser
import inference

class ProgramInference:
	def __init__(self):
		self.inf = inference.Inference()

	def convert_expr(self, expr):
		kind = expr.name
		if kind == "appExpr":
			return inference.Expr(
				"app",
				[self.convert_expr(expr["fn"])] + [
					self.convert_expr(arg)
					for arg in expr["args"]
				],
			)
		elif kind == "qualName":
			arg_name, = expr.contents
			return inference.Expr("var", arg_name)
		elif kind == "letExpr":
			pass
		elif kind == "matchExpr":
			pass
		elif kind == "lambdaExpr":
			#arg_name, arg_type_annot = expr["args"]
			return inference.Expr(
				"abs",
				[
					inference.Expr("var", arg_name)
					for arg_name, arg_type_annot in expr["args"]
				] + [self.convert_expr(expr["result"])],
			)

	def infer(self, ast):
		inference_expression = self.convert_expr(ast)
		result = self.inf.J({}, inference_expression)
		result = self.inf.most_specific_type(result)
		print result

if __name__ == "__main__":
	p = argparse.ArgumentParser()
	p.add_argument("source")
	args = p.parse_args()

	with open(args.source) as f:
		source = f.read()

	ast = parser.parse(source, kind="expr")
	prog_inf = ProgramInference()
	prog_inf.infer(ast)

