#!/usr/bin/python
"""
jit.py

Contains logic for JITing core programs down into LLVM IR.
"""

import argparse
import llvmlite.binding

import parsing
import core
import inference
import prelude
import lower
import utils
from runtime import runtime

# Make our runtime symbols accessible to the llvm backend.
llvmlite.binding.load_library_permanently(runtime.dll_path)
llvmlite.binding.initialize()
llvmlite.binding.initialize_native_target()
llvmlite.binding.initialize_native_asmprinter()

class LLVM:
	def __init__(self):
		self.target = llvmlite.binding.Target.from_default_triple()
		self.target_machine = self.target.create_target_machine()
		self.backing_mod = llvmlite.binding.parse_assembly("")
		self.engine = llvmlite.binding.create_mcjit_compiler(self.backing_mod, self.target_machine)

	def compile(self, ir):
		mod = llvmlite.binding.parse_assembly(ir)
		mod.verify()
		self.engine.add_module(mod)
		self.engine.finalize_object()
		self.engine.run_static_constructors()
		return LLVM.ModuleHandle(self, mod)

	def get_function(self, name):
		return self.engine.get_function_address(name)

	class ModuleHandle:
		def __init__(self, parent, mod):
			self.parent = parent
			self.mod = mod

		def __del__(self):
			self.parent.engine.remove_module(self.mod)

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

