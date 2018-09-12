#!/usr/bin/python

import argparse
import parser
import inference
import dependency

class ProgramInference:
	def __init__(self):
		self.inf = inference.Inference()
		self.type_mappings = {}

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
			arg_name, = expr["name"].contents
			return inference.Expr("let", [
				inference.Expr("var", arg_name),
				self.convert_expr(expr["expr1"]),
				self.convert_expr(expr["expr2"]),
			])
		elif kind == "matchExpr":
			raise NotImplementedError("Match not implemented.")
		elif kind == "lambdaExpr":
			return inference.Expr(
				"abs",
				[
					inference.Expr("var", arg_name)
					for arg_name, arg_type_annot in expr["args"]
				] + [self.convert_expr(expr["result"])],
			)

	def infer_expr(self, ast, gamma={}):
		inference_expression = self.convert_expr(ast)
#		print "Inferring:", inference_expression
		result = self.inf.J(gamma, inference_expression)
#		result = self.inf.most_specific_type(result)
		return result

	def get_dependencies(self, ast):
		if isinstance(ast, list):
			v = set()
			for x in ast:
				v |= self.get_dependencies(x)
			return v
		kind = ast.name
		if kind == "letStatement":
			return self.get_dependencies(ast["expr"])
		elif kind == "appExpr":
			return self.get_dependencies(ast["args"]) | self.get_dependencies(ast["fn"])
		elif kind == "lambdaExpr":
			lambda_binders = set(arg_name for arg_name, type_annot in ast["args"])
			return self.get_dependencies(ast["result"]) - lambda_binders
		elif kind == "qualName":
			var_name, = ast.contents
			return set([var_name])
		raise NotImplementedError("Unhandled case in get_dependencies: %r" % (ast,))

	def infer_block(self, ast):
		# Compute dependencies.
		dep_manager = dependency.DependencyManager()
		name_to_statement = {}
		for statement in ast:
			assert statement.name == "letStatement"
			var_name, = statement["name"].contents
			if var_name in name_to_statement:
				raise ValueError("Redefinition of: %s" % (var_name,))
			name_to_statement[var_name] = statement

			dependencies = self.get_dependencies(statement)
			for dep in dependencies:
				assert isinstance(var_name, str)
				assert isinstance(dep, str)
				dep_manager.add_dep(var_name, dep)

		# Compute an order to perform inference in.
		strongly_connected_components = dep_manager.strongly_connected_components()
		print "Strongly connected components:", strongly_connected_components

		# Initialize our context as empty.
		gamma = {}

		# Compute typing for each strongly connected component together.
		for component in strongly_connected_components:
			print "\n=== Inference for component:", component
			component_statements = [name_to_statement[name] for name in component]
			# Add fresh monotype variables to our system for the new statements.
			for statement in component_statements:
				assert statement.name == "letStatement"
				var_name, = statement["name"].contents
				new_type_var = self.type_mappings[var_name] = self.inf.new_type()
				gamma[inference.Expr("var", var_name)] = inference.PolyType(set(), new_type_var)
			# Apply inference, and add constraints on our monotype variables.
			for statement in component_statements:
				var_name, = statement["name"].contents
				resultant_type = self.infer_expr(statement["expr"], gamma=gamma)
				self.inf.equate(self.type_mappings[var_name], resultant_type)
			# Generalize from the monotypes in the component to new polytypes, and update the context.
			for statement in component_statements:
				var_name, = statement["name"].contents
				type_var = self.type_mappings[var_name]
				poly_type = self.inf.contextual_generalization(gamma, self.inf.most_specific_type(type_var))
				gamma[inference.Expr("var", var_name)] = poly_type
				print "Adding:", var_name, ":", poly_type

			print "All monotypes so far:"
			for name, t in self.type_mappings.iteritems():
				print "\t%s : %s" % (name, self.inf.most_specific_type(t))

if __name__ == "__main__":
	p = argparse.ArgumentParser()
	p.add_argument("source")
	args = p.parse_args()

	with open(args.source) as f:
		source = f.read()

	ast = parser.parse(source, kind="codeBlock")
	prog_inf = ProgramInference()
	prog_inf.infer_block(ast)

