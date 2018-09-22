#!/usr/bin/python
"""
jit.py

Contains logic for JITing core programs down into LLVM IR.
"""

import os, argparse
import llvmlite.binding

import parsing
import core
import inference
import prelude
import lower
import utils
from runtime import runtime

llvmlite.binding.initialize()
llvmlite.binding.initialize_native_target()
llvmlite.binding.initialize_native_asmprinter()

class LLVM:
	def __init__(self):
		self.target = llvmlite.binding.Target.from_default_triple()
		self.target_machine = self.target.create_target_machine()
		self.backing_mod = llvmlite.binding.parse_assembly("")
		self.engine = llvmlite.binding.create_mcjit_compiler(self.backing_mod, self.target_machine)
		self.permanent_module_handles = []
		self.prelude_ir = ""

	def add_to_prelude(self, ir):
		self.prelude_ir += ir

	def compile(self, ir, make_permanent=False):
		mod = llvmlite.binding.parse_assembly(self.prelude_ir + ir)
		mod.verify()
		self.engine.add_module(mod)
		self.engine.finalize_object()
		self.engine.run_static_constructors()
		module_handle = LLVM.ModuleHandle(self, mod)
		if make_permanent:
			self.permanent_module_handles.append(module_handle)
		return module_handle

	def get_function(self, name):
		return self.engine.get_function_address(name)

	class ModuleHandle:
		def __init__(self, parent, mod):
			self.parent = parent
			self.mod = mod

		def __del__(self):
			self.parent.engine.remove_module(self.mod)

class FunctionIR:
	def __init__(self, name, arg_names):
		self.name = name
		self.arg_names = arg_names
		self.global_defs = []
		self.ir = []
		self.tmp = 0

		# Build the header.
		self.add("define %L11Obj* @{0}(%L11Obj* %self, i32 %arg_count, %L11Obj** %arguments) {{\n".format(self.name))
		# Check that we have the right number of arguments.
		self.add("\t; verify argument count\n")
		self.add("\t%args_good_flag = icmp eq i32 {0}, %arg_count\n".format(len(arg_names)))
		self.add("\tbr i1 %args_good_flag, label %ArgsGood, label %ArgsBad\n")
		self.add("ArgsBad:\n")
		error_string = self.get_string_ptr("bad argument count")
		self.add("\tcall void @l11_panic(i8* %{0})\n".format(error_string))
		self.add("\tret %L11Obj* undef\n")
		self.add("ArgsGood:\n")
		# Get the arguments.
		for i, arg_name in enumerate(self.arg_names):
			tmp = self.get_tmp()
			self.add("\t; unpack arg {0}\n".format(arg_name))
			self.add("\t%{0} = getelementptr %L11Obj*, %L11Obj** %arguments, i32 {1}\n".format(tmp, i))
			self.add("\t%{0} = load %L11Obj*, %L11Obj** %{1}\n".format(arg_name, tmp))

	def finalize(self):
		# Exhibit UB on falling off the end.
		self.add("\tret %L11Obj* undef\n")
		self.add("}")

	def get_tmp(self):
		self.tmp += 1
		return "tmp.%i" % (self.tmp,)

	def apply(self, fn_obj, args):
		self.add("\t; {0} applied to {1}\n".format(fn_obj, args))
		args_array = self.get_tmp()
		self.add("\t%{0} = alloca %L11Obj*, i32 {1}\n".format(args_array, len(args)))
		for i, arg in enumerate(args):
			arg_insert_ptr = self.get_tmp()
			self.add("\t%{0} = getelementptr %L11Obj*, %L11Obj** %{1}, i32 {2}\n".format(
				arg_insert_ptr,
				args_array,
				i,
			))
			self.add("\tstore %L11Obj* %{0}, %L11Obj** %{1}\n".format(arg, arg_insert_ptr))
		result = self.get_tmp()
		self.add("\t%{0} = call %L11Obj* @obj_apply(%L11Obj* %{1}, i32 {2}, %L11Obj** %{3})\n".format(
			result,
			fn_obj,
			len(args),
			args_array,
		))
		return result

	def add_string(self, s):
		name = "str." + self.get_tmp()
		self.add_global("@{0} = private unnamed_addr constant [{1} x i8] {2}\n".format(
			name,
			len(s),
			"[{0}]".format(
				", ".join("i8 {0}".format(ord(c)) for c in s),
			),
		))
		return name

	def get_string_ptr(self, s):
		string_name = self.add_string(s)
		string_ptr = self.get_tmp()
		self.add("\t%{0} = getelementptr [{1} x i8], [{1} x i8]* @{2}, i32 0, i32 0\n".format(
			string_ptr,
			len(s),
			string_name,
		))
		return string_ptr

	def lookup(self, obj, name):
		self.add("\t; lookup {0} {1}\n".format(obj, name))
		string_ptr = self.get_string_ptr(name)
		result = self.get_tmp()
		self.add("\t%{0} = call %L11Obj* @obj_lookup(%L11Obj* %{1}, i8* %{2}, i64 {3})\n".format(
			result,
			obj,
			string_ptr,
			len(name)
		))
		return result

	def inc_ref(self, obj):
		self.add("\tcall void @obj_inc_ref(%L11Obj* %{0})\n".format(obj))

	def dec_ref(self, obj):
		self.add("\tcall void @obj_dec_ref(%L11Obj* %{0})\n".format(obj))

	def return_obj(self, obj):
		self.add("\tret %L11Obj* %{0}\n".format(obj))

	def add(self, s):
		self.ir.append(s)

	def add_global(self, s):
		self.global_defs.append(s)

	def format(self):
		return "".join(self.global_defs) + "\n" + "".join(self.ir)

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
	llvm = LLVM()

	# Load up the runtime interface.
	llvmlite.binding.load_library_permanently(runtime.dll_path)
	with open(os.path.join("runtime", "interface_runtime.ll")) as f:
		prelude_ir = f.read()
	llvm.add_to_prelude(prelude_ir)

	f = FunctionIR("id", ["x", "y"])
	result = f.apply("x", ["y", "x"])
	result = f.lookup(result, "asdf")
	f.dec_ref(result)
	f.return_obj(result)
	f.finalize()
	ir = f.format()
	print ir

#	mod = llvm.compile("""
#define i64 @car(%L11Obj* %obj) {
#	%ptr = getelementptr %L11Obj, %L11Obj* %obj, i32 0, i32 0
#	%value = load i64, i64* %ptr
#	call void @debug_print_num(i64 %value)
#	ret i64 %value
#}
#""")
	mod = llvm.compile(ir)
	fp = llvm.get_function("id")
	print "Function pointer:", fp

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

