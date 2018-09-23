#!/usr/bin/python

import utils
import llvmlite.binding
import jitcore

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

class Specialization:
	def __init__(self, infos):
		self.infos = infos

class Function:
	def __init__(self, name, snippet, arg_count):
		self.name = name
		self.snippet = snippet
		self.arg_count = arg_count

	def compile(self):
		dest = jitcore.IRDestination()
		dest.add("define %L11Obj* @{0}(%L11Obj* %self, i32 %arg_count, %L11Obj** %arguments) {{\n".format(self.name))

		# Check the argument count.
		dest.add("\t%good_arg_count = icmp eq i32 %arg_count, {0}\n".format(self.arg_count))
		dest.add("\tbr i1 %good_arg_count, label %GoodArgCount, label %BadArgCount\n")
		dest.add("BadArgCount:\n")
		error_ptr = dest.get_string_ptr("Bad argument count.")
		dest.add("\tcall void @l11_panic(i8* {0})\n".format(error_ptr))
		dest.add("\tunreachable\n")
		dest.add("GoodArgCount:\n")

		# Unpack the arguments into registers.
		args = []
		for i in xrange(self.arg_count):
			load_ptr = dest.new_tmp()
			dest.add("\t{0} = getelementptr %L11Obj*, %L11Obj** %arguments, i32 {1}\n".format(
				load_ptr, i
			))
			arg = dest.new_tmp()
			dest.add("\t{0} = load %L11Obj*, %L11Obj** {1}\n".format(arg, load_ptr))
			args.append(arg)
		assumptions = jitcore.AssumptionContext()
		result, = self.snippet.instantiate(dest, assumptions, args)
		# Force the result into a box.
		result, = jitcore.ForceBoxSnippet().instantiate(dest, assumptions, [result])
		dest.add("\tret %L11Obj* {0}\n".format(result))
		dest.add("}\n")

		ir = dest.format()

		with open("/tmp/demo.ll", "w") as out_f:
			with open("interface_runtime.ll") as f:
				out_f.write(f.read())
			out_f.write(ir)
			out_f.write("\n")

