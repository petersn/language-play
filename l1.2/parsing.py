#!/usr/bin/python

import easy
import lark

with open("grammar.txt") as f:
	grammar_text = f.read()

# Strip comments from the grammar.
grammar_text = "\n".join(
	line for line in grammar_text.split("\n")
	if not line.strip().startswith("//")
)
term_parser = lark.Lark(grammar_text, start="term")
# FIXME: Is there some way to reuse with the above grammar?
vernac_parser = lark.Lark(grammar_text, start="vernacular")

def unpack_typed_params(ctx, typed_params):
	"""unpack_typed_params(typed_params) -> [(var1, ty1), ...]"""
	results = []
	for child in typed_params.children:
		if child.data == "untyped_param":
			var_name, = child.children
			results.append((easy.Var(str(var_name)), easy.Hole()))
		elif child.data == "param_group":
			ty = unpack_term_ast(ctx, child.children[-1])
			for var_name in child.children[:-1]:
				results.append((easy.Var(str(var_name)), ty))
		else:
			assert False
	return results

def unpack_typed_params_to_Parameters(ctx, typed_params):
	typed_params = unpack_typed_params(ctx, typed_params)
	names, types = [], []
	for n, t in typed_params:
		names.append(n.var)
		types.append(t)
	return easy.Parameters(names, types)

def wrap_with_typed_params(ctx, typed_params, term, mode):
	assert mode in ("dependent_product", "abstraction")
	typed_params = unpack_typed_params(ctx, typed_params)
	for var, ty in typed_params[::-1]:
		term = {
			"dependent_product": easy.DependentProduct,
			"abstraction": easy.Abstraction,
		}[mode](var, ty, term)
	return term

def unpack_optional_type_annotation(ctx, annot):
	if not annot.children:
		return easy.Hole()
	annot_ty_ast, = annot.children
	return unpack_term_ast(ctx, annot_ty_ast)

def unpack_term_ast(ctx, ast):
	# This is a binding of some sort.
	if isinstance(ast, lark.lexer.Token):
		name = str(ast)
		if name.startswith("Type"):
			universe_index = int(name[4:])
			return easy.SortType(universe_index)
		if name == "Prop":
			return easy.SortProp()
		# XXX: Make sure the name is bound!
#		if not ctx.contains_def(easy.Var(name)) and not ctx.contains_ty(easy.Var(name)):
#			raise ValueError("Unbound name: %s" % (name,))
		return easy.Var(name)
	if ast.data in ("dependent_product", "abstraction"):
		typed_params, result_ty = ast.children
		result = unpack_term_ast(ctx, result_ty)
		return wrap_with_typed_params(ctx, typed_params, result, ast.data)
	if ast.data == "arrow":
		A, B = [unpack_term_ast(ctx, child) for child in ast.children]
		return easy.DependentProduct(easy.Var("!"), A, B)
	if ast.data == "application":
		fn, arg = [unpack_term_ast(ctx, child) for child in ast.children]
		return easy.Application(fn, arg)
	if ast.data == "annotation":
		x, ty = [unpack_term_ast(ctx, child) for child in ast.children]
		return easy.Annotation(x, ty)
	if ast.data == "constructor":
		# XXX: Check name presense.
		ind_name, con_name = map(str, ast.children)
		return easy.ConstructorRef(ind_name, con_name)
	if ast.data == "match":
		ast_matchand, ast_extensions, ast_arms = ast.children
		match_term = unpack_term_ast(ctx, ast_matchand)
		extensions = {
			"as": easy.Hole(),
			"in": easy.Hole(),
			"return": easy.Hole(),
		}
		# Process extensions.
		for child in ast_extensions.children:
			extension_term, = child.children
			extension_term = unpack_term_ast(ctx, extension_term)
			extensions[{
				"as_term": "as",
				"in_term": "in",
				"return_term": "return",
			}[child.data]] = extension_term
		# Process the arms.
		arms = []
		for arm in ast_arms.children:
			arm_pattern, arm_result = [unpack_term_ast(ctx, child) for child in arm.children]
			arms.append(easy.Match.Arm(arm_pattern, arm_result))
		return easy.Match(
			match_term,
			extensions["as"],
			extensions["in"],
			extensions["return"],
			arms,
		)
	if ast.data == "fix":
		name, typed_params, optional_type_annotation, body = ast.children
		parameters = unpack_typed_params_to_Parameters(ctx, typed_params)
		return_ty = unpack_optional_type_annotation(ctx, optional_type_annotation)
		body = unpack_term_ast(ctx, body)
		return easy.Fix(
			str(name),
			parameters,
			return_ty,
			body,
		)
	raise NotImplementedError("Unhandled AST node: %r" % (ast.data,))

if __name__ == "__main__":
	test_strings = [
		"(x :: y)",
		"forall x, A -> B",
		"A -> B -> C",
		# Unfortunately currently this one parses the x -> y part wrong.
		"X -> forall a (b c : nat) T (e : T), x -> y",
		"match x ~ as y return P with O => y | S x' => S (add x' y) end",
	#	"fix add x y : nat ~ := match x with O => y | S x' => S (add x' y) end",
	]

	for s in test_strings:
		ctx = easy.Context()
		print "Testing:", s
		ast = term_parser.parse(s)
		result = unpack_term_ast(ctx, ast)
		print "Result:", result
		print

