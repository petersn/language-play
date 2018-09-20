#!/usr/bin/python
"""
jit.py

Contains logic for JITing core programs down into LLVM IR.
"""

import argparse
import parsing
import core
import inference
import prelude
import lower
import utils

class JIT:
	def compile_top_level(self, top_level):
		for decl in top_level.root_block.entries:
			self.compile_func(decl.expr, decl.type_annotation)

	def compile_func(self, func, func_poly_type):
		assert isinstance(func, core.AbsExpr)
		print func
		print func_poly_type
		print func_poly_type.is_concrete()

if __name__ == "__main__":
	p = argparse.ArgumentParser()
	p.add_argument("source")
	args = p.parse_args()

	with open(args.source) as f:
		source = f.read()

	ast = parsing.parse(source)

	lowerer = lower.Lowerer()
	lowerer.add_code_block(lowerer.top_level.root_block, ast)

	print "=" * 20, "Pre-inference:"
	print utils.pretty(lowerer.top_level)

	# Do inference.
	gamma = prelude.make_gamma()
	inf = inference.Inference()
	inf.infer_code_block(gamma, lowerer.top_level.root_block)

	print "=" * 20, "Post-inference:"

	print utils.pretty(lowerer.top_level)

	jit = JIT()
	jit.compile_top_level(lowerer.top_level)

