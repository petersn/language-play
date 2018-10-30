#!/usr/bin/python

import sys, argparse, functools
import parsing
import easy

vernacular_table = {}
def vernacular_handler(vernacular_name):
	def dec(f):
		vernacular_table[vernacular_name] = f
		return f
	return dec

@vernacular_handler("vernac_definition")
def vernac_definition(context, vernac):
	name, typed_params, type_annotation, body = vernac.children
	# TODO: Properly unfold the typed_params as abstractions around the body.
	# TODO: Properly check the type annotation.
	body = parsing.unpack_term_ast(context, body)
	body = parsing.wrap_with_typed_params(context, typed_params, body, "abstraction")

	context.extend_def(easy.Var(str(name)), body, in_place=True)

@vernacular_handler("vernac_axiom")
def vernac_axiom(context, vernac):
	name, ty = vernac.children
	ty = parsing.unpack_term_ast(context, ty)
	context.extend_def(easy.Var(str(name)), easy.Axiom(ty), in_place=True)

@vernacular_handler("vernac_inductive")
def vernac_inductive(context, vernac):
	name, typed_params, arity, constructors = vernac.children

	# Unpack the typed_params into the inductive's parameters.
	typed_params = parsing.unpack_typed_params(context, typed_params)
	names, types = [], []
	for n, t in typed_params:
		names.append(n)
		types.append(t)
	parameters = easy.Parameters(names, types)

	arity = parsing.unpack_term_ast(context, arity)
	ind = easy.Inductive(
		context,
		str(name),
		parameters,
		arity,
	)

	# Add the inductive in globally before we build constructors
	# because the constructors must reference the inductive itself.
	context.extend_def(easy.Var(str(name)), easy.InductiveRef(str(name)), in_place=True)

	# Add the constructors.
	for constructor in constructors.children:
		con_name, con_typed_params, con_type = constructor.children
		con_type = parsing.unpack_term_ast(context, con_type)
		# In this case the typed params are just sugar for extending the type,
		# so apply the con_typed_params as additional products around the type.
		con_type = parsing.wrap_with_typed_params(context, con_typed_params, con_type, "dependent_product")
		ind.add_constructor(str(con_name), con_type)
	print "Added:"
	ind.pprint()

@vernacular_handler("vernac_infer")
def vernac_infer(context, vernac):
	term, = vernac.children
	term = parsing.unpack_term_ast(context, term)
	ty = term.infer(context)
	print "Infer: %s : %s" % (term, ty)

@vernacular_handler("vernac_check")
def vernac_check(context, vernac):
	term, ty = [parsing.unpack_term_ast(context, i) for i in vernac.children]
	try:
		term.check(context, ty)
		print "Successful type check: %s : %s" % (term, ty)
	except Exception, e:
		print "Type check failure:", e

@vernacular_handler("vernac_eval")
def vernac_eval(context, vernac):
	term, = vernac.children
	term = parsing.unpack_term_ast(context, term)
	term = term.normalize(context, easy.EvalStrategy.CBV)
	print "Eval:", term

def interpret(path):
	with open(path) as f:
		code = "".join(
			line for line in f
			if not line.strip().startswith("#")
		)
	context = easy.Context()
	vernacs = parsing.vernac_parser.parse(code)
	for vernac in vernacs.children:
		vernacular_table[vernac.data](context, vernac)

if __name__ == "__main__":
	interpret(sys.argv[1])

