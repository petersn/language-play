#!/usr/bin/python
"""
jit.py

Contains logic for JITing core programs down into jitcore.Snippets, which in turn produce IR.
"""

import os, argparse
import parsing
import core
import inference
import prelude
import lower
import utils
from jit import jitcore
from jit import jitstdlib
from jit import jitllvm
from jit import runtime

class AbstractionJIT:
	def __init__(self, abs_expr):
		assert isinstance(abs_expr, core.AbsExpr)
		self.names = {}
		argument_count = len(abs_expr.arg_names)
		self.seq = jitcore.SequenceSnippet(argument_count)
		for arg_name, handle in zip(abs_expr.arg_names, self.seq.get_inputs()):
			self.names[arg_name] = handle
		result = self.build(abs_expr.result_expr)
		self.seq.set_outputs([result])

	def build_literal(self, literal):
		if isinstance(literal, int):
			result, = self.seq(1, jitstdlib.make_int_snippet_factory(literal))
			return result
		raise NotImplementedError("Unhandled literal: %r" % (literal,))

	def build(self, expr):
		if isinstance(expr, core.BlockExpr):
			return self.build(expr.code_block)
		elif isinstance(expr, core.CodeBlock):
			for entry in expr.entries:
				result = self.build(entry)
			return result
		elif isinstance(expr, core.Declaration):
			result = self.names[expr.name] = self.build(expr.expr)
			return result
		elif isinstance(expr, core.ReturnStatement):
			result = self.build(expr.expr)
			# TODO: Think carefully about a more type aware thing to do here.
			boxed_result, = self.seq(1, jitcore.ForceBoxSnippet(), result)
			self.seq(0, jitcore.FormatSnippet(1, 0, "\tret %L11Obj* {in0}\n"), boxed_result)
			# XXX: Is this the right return value? Is there any?
			# Control flow is hard. :/
			return boxed_result
		elif isinstance(expr, core.VarExpr):
			return self.names[expr.name]
		elif isinstance(expr, core.LiteralExpr):
			return self.build_literal(expr.literal)
		elif isinstance(expr, core.MethodCallExpr):
			obj = self.build(expr.fn_expr)
			args = [self.build(arg) for arg in expr.arg_exprs]
			result, = self.seq(1, jitcore.MethodSnippet(expr.method_name), obj, *args)
			return result
		raise NotImplementedError("Don't know how to JIT: %r" % (expr.__class__,))

	def get_snippet(self):
		return self.seq

class JIT:
	def compile_top_level(self, top_level):
		for decl in top_level.root_block.entries:
			result = self.compile_func(decl.name, decl.expr, decl.type_annotation)
		return result

	def compile_func(self, name, func, func_poly_type):
		abs_jit = AbstractionJIT(func)
		snippet = abs_jit.get_snippet()
		arg_count = len(func.arg_names)
		function = jitllvm.Function(name, snippet, arg_count)
		function.compile()
		return function
#		return abs_jit.get_snippet()
#		assert isinstance(func, core.AbsExpr)
#		contents = 
#		return self.to_snippet(func)
#		print func.result_expr
#		print dir(func)
#		print func_poly_type
#		print func_poly_type.is_concrete()

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

	print "=" * 20, "JITing."

	jitcore.initialize()

	jit = JIT()
	function = jit.compile_top_level(lowerer.top_level)
	#final_snippet = jit.compile_top_level(lowerer.top_level)

	print "Function built!"

	print function.function_pointer

#	# Test out this snippet.
#	dest = jitcore.IRDestination()
#	assumptions = jitcore.AssumptionContext()
#	final_snippet.instantiate(dest, assumptions, ["%x"])

#	print dest.format()

