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
	body = parsing.unpack_term_ast(context, body)
	context.extend_def(easy.Var(name), body)

@vernacular_handler("vernac_axiom")
def vernac_axiom(context, vernac):
	name, ty = vernac.children
	ty = parsing.unpack_term_ast(context, ty)
	context.extend_def(easy.Var(name), ty)

@vernacular_handler("vernac_inductive")
def vernac_inductive(context, vernac):
	raise NotImplementedError

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

