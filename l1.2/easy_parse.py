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
		elif toks[i].startswith("Type"):
			universe_index = int(toks[i][4:])
			return easy.SortType(universe_index), i + 1
		elif toks[i] == "Prop":
			return easy.SortProp(), i + 1
		elif toks[i].startswith("@"):
			ind_name = toks[i][1:]
			assert toks[i+1] == "."
			con_name = toks[i + 2]
			return easy.InductiveConstructor(ind_name, con_name), i + 3
		elif toks[i] == "match":
			matchand, i = parse(toks, i + 1)
			assert toks[i] == "as"
			as_term, i = parse(toks, i + 1)
			assert toks[i] == "in"
			in_term, i = parse(toks, i + 1)
			assert toks[i] == "return"
			return_term, i = parse(toks, i + 1)
			assert toks[i] == "with"
			i += 1
			arms = []
			while toks[i] == "|":
				pattern, i = parse(toks, i + 1)
				assert toks[i] == "=>"
				result, i = parse(toks, i + 1)
				arms.append(easy.Match.Arm(pattern, result))
			assert toks[i] == "end", "Expected end: %r" % (toks[i],)
			match_term = easy.Match(matchand, as_term, in_term, return_term, arms)
			return match_term, i + 1
		return easy.Var(toks[i]), i + 1

	term, i = parse(s, 0)
	assert i == len(s)
	return term

