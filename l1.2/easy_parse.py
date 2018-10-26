#!/usr/bin/python

import easy

def parse_term(s):
	for op in "():.":
		s = s.replace(op, " %s " % op)
	s = s.strip().split()
	name_mapping = {}

	def parse(toks, i):
		if toks[i] == "(" and toks[i+1] in ["fun", "forall"]:
			var = easy.Var(toks[i+2])
			assert toks[i+3] == ":"
			type_term, j = parse(toks, i + 4)
			assert toks[j] == "."
			expr_term, k = parse(toks, j + 1)
			assert toks[k] == ")"
			kind = {"fun": easy.Abs, "forall": easy.DepProd}[toks[i+1]]
			return kind(var, type_term, expr_term), k + 1
		elif toks[i] == "(":
			applicand, j = parse(toks, i + 1)
			applicee, k = parse(toks, j)
			assert toks[k] == ")"
			return easy.App(applicand, applicee), k + 1
		elif toks[i] == "Type":
			return easy.RootType(), i + 1
		return easy.Var(toks[i]), i + 1

	term, i = parse(s, 0)
	assert i == len(s)
	return term

