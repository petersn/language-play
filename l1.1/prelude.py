#!/usr/bin/python

import core
import inference

def make_gamma():
	gamma = inference.Gamma()
	gamma[core.VarExpr("nil")] = core.PolyType(set(), core.AppType("nil", []))
	return gamma

