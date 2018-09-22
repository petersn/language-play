#!/usr/bin/python
"""
jit.py

Basic JIT experimentation.
"""

import os, argparse, pprint, enum, inspect
import llvmlite.binding
import runtime
import jitstdlib

l11obj_header_size = 8 + 8

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

class Kind:
	def __init__(self, name, kind_number, bytes_extra=0):
		self.name = name
		self.kind_number = kind_number
		self.bytes_extra = bytes_extra
		self.members = {}

	def total_byte_length(self):
		return l11obj_header_size + self.bytes_extra

	def __getitem__(self, key):
		return self.members[key]

	def __setitem__(self, key, value):
		assert isinstance(value, Snippet)
		self.members[key] = value

	def __contains__(self, key):
		return key in self.members

	def __repr__(self):
		return "<Kind %s>" % (self.name,)

class KindTable:
	def __init__(self):
		self.kind_table = {}

	def __getitem__(self, key):
		return self.kind_table[key]

	def __contains__(self, key):
		return key in self.kind_table

	def new_kind(self, name):
		kind_number = len(self.kind_table)
		kind = self.kind_table[name] = Kind(name, kind_number)
		runtime.l11_new_kind(kind_number)

class ValueType(enum.Enum):
	L11OBJ = 1
	UNBOXED_INT = 2

value_type_to_llvm_type = {
	ValueType.L11OBJ: "%L11Obj*",
	ValueType.UNBOXED_INT: "i64",
}

# Our static knowledge about an identifier comes in three levels:
# 1) First, we have a "type", from ValueType.
# 2) If the type is L11OBJ then we have a "kind", which is a Kind.
# 3) If the type is anything other than L11OBJ then we may or may not have an explicit compile-time value.
# One day we'll allow compile-time values for L11OBJ, but for now I'm not dealing with that.
# In terms of implications: A name being in either name_to_kind or name_to_value implies that the name is also in name_to_type.
# Therefore, we use name_to_type as our authoritative reference for what identifiers are real.
class AssumptionContext:
	def __init__(self):
		# Stores the type (a ValueType) for each name.
		self.name_to_type = {}
		# Stores the kind (a Kind) for each name that is of type ValueType.L11OBJ
		self.name_to_kind = {}
		# Stores an explicit compile-time value for each name that is of a type OTHER than ValueType.L11OBJ
		self.name_to_value = {}
		self.sanity_check()

	def sanity_check(self):
		# Ensure name_to_type : Dict[str, ValueType]
		for k, v in self.name_to_type.iteritems():
			assert isinstance(k, str)
			assert isinstance(v, ValueType)
		# Ensure name_to_kind : Dict[str, Kind]
		for k, v in self.name_to_kind.iteritems():
			assert isinstance(k, str)
			assert isinstance(v, Kind)
			# Further assert that the key is also in name_to_type, and has type ValueType.L11OBJ.
			assert self.name_to_type[k] == ValueType.L11OBJ
		# Ensure name_to_value : Dict[str, object]
		for k in self.name_to_value.iterkeys():
			assert isinstance(k, str)
			# Further assert that the key is also in name_to_type, and has a type OTHER than ValueType.L11OBJ
			assert self.name_to_type[k] != ValueType.L11OBJ

	def set_type(self, name, ty):
		assert isinstance(name, str)
		# Do not allow reassignment!
#		assert name not in self.name_to_type, "Reassignment isn't allowed!"
		self.name_to_type[name] = ty

	def get_type(self, name):
		assert isinstance(name, str)
		return self.name_to_type.get(name, ValueType.L11OBJ)

	def set_kind(self, name, kind):
		self.set_type(name, ValueType.L11OBJ)
		self.name_to_kind[name] = kind

	def get_kind(self, name):
		"""get_kind(name: str) -> Kind

		Gives the kind for a name whose type is ValueType.L11OBJ.
		If the type is anything else then an exception is raised.
		"""
		assert self.get_type(name) == ValueType.L11OBJ, "Only L11Obj typed variables can have a kind!"
		return self.name_to_kind[name]

	def set_concrete_value(self, name, value):
		assert self.get_type(name) != ValueType.L11OBJ, "L11Obj typed variables cannot have a concrete value!"
		self.name_to_value[name] = value

	def get_concrete_value(self, name):
		return self.name_to_value[name]

	def is_L11Obj(self, name):
		return self.get_type(name) == ValueType.L11OBJ

	def has_known_kind(self, name):
		"""has_known_kind(name: str) -> bool

		Returns if the given name is known to be an L11Obj, and its Kind is known statically.
		"""
#		assert self.is_L11Obj(name)
#		return name in self.name_to_kind
		return self.is_L11Obj(name) and name in self.name_to_kind

	def has_concrete_value(self, name):
		return name in self.name_to_value

class IRDestination:
	def __init__(self):
		self.ir = []
		self.global_ir = []
		self.string_table = {}
		self.tmp = 0

	def new_name(self, prefix="name", count=None):
		if count != None:
			return [self.new_name(prefix=prefix) for _ in xrange(count)]
		self.tmp += 1
		return "{0}.{1}".format(prefix, self.tmp)

	def new_tmp(self, count=None):
		return self.new_name(prefix="%tmp", count=count)

	def new_label(self, count=None):
		return self.new_name(prefix="Label", count=count)

	def add(self, s):
		self.ir.append(s)

	def add_global(self, s):
		self.global_ir.append(s)

	def add_string(self, s):
		if s not in self.string_table:
			name = self.new_name(prefix="@str")
			self.add_global("{0} = private unnamed_addr constant [{1} x i8] {2}\n".format(
				name,
				len(s),
				"[{0}]".format(
					", ".join("i8 {0}".format(ord(c)) for c in s),
				),
			))
			self.string_table[s] = name
		return self.string_table[s]

	def get_string_ptr(self, s):
		string_name = self.add_string(s)
		string_ptr = self.new_tmp()
		self.add("\t{0} = getelementptr [{1} x i8], [{1} x i8]* {2}, i32 0, i32 0\n".format(
			string_ptr,
			len(s),
			string_name,
		))
		return string_ptr

	def format(self):
		return "".join(self.global_ir) + "\n" + "".join(self.ir)

class Snippet:
	def instantiate(self, dest, assumptions, inputs):
		raise NotImplementedError("doesn't implement instantiate")

class SequenceSnippet(Snippet):
	def __init__(self, input_count):
		self.sequence = []
		self.handle_counter = 0
		self.input_handles = [SequenceSnippet.ValueHandle(self) for _ in xrange(input_count)]

	def __call__(self, output_count, snippet, *inputs):
		assert isinstance(snippet, Snippet)
		assert all(isinstance(handle, SequenceSnippet.ValueHandle) and handle.parent == self for handle in inputs)
		outputs = [SequenceSnippet.ValueHandle(self) for _ in xrange(output_count)]
		self.sequence.append((snippet, inputs, outputs))
		return outputs

	def get_inputs(self):
		return self.input_handles

	def set_outputs(self, handles):
		self.output_handles = handles

	def instantiate(self, dest, assumptions, inputs):
		variable_table = {}
		assert len(inputs) == len(self.input_handles)
		for input_handle, input_var in zip(self.input_handles, inputs):
			variable_table[input_handle] = input_var
		# Processes our entire sequence.
		for snippet, input_handles, output_handles in self.sequence:
			input_vars = [variable_table[input_handle] for input_handle in input_handles]
			output_vars = snippet.instantiate(dest, assumptions, input_vars)
			if output_vars is None:
				print "WARNING: Snippet in sequence returned None:", snippet
				print "Did you forget to return outputs in your snippet?"
			assert len(output_handles) == len(output_vars), "Handle mismatch: %r vs %r" % (output_handles, output_vars)
			for output_handle, output_var in zip(output_handles, output_vars):
				variable_table[output_handle] = output_var
		# Return the appropriate variables.
		return [variable_table[output_handle] for output_handle in self.output_handles]

	class ValueHandle:
		def __init__(self, parent):
			self.parent = parent
			self.i = parent.handle_counter
			parent.handle_counter += 1

		def __repr__(self):
			return "<handle %i>" % (self.i,)

def snippet_maker(f):
	argument_count = len(inspect.getargspec(f).args)
	seq = SequenceSnippet(argument_count - 1)
	inputs = seq.get_inputs()
	outputs = f(seq, *inputs)
	seq.set_outputs(outputs)
	return seq

class ApplySnippet(Snippet):
	def instantiate(self, dest, assumptions, inputs):
		fn = inputs[0]
		args = inputs[1:]
		# Check if we know the type of the function.
		if assumptions.has_known_kind(fn):
			fn_kind = assumptions.get_kind(fn)
			if "apply" not in fn_kind:
				raise ValueError("Kind %r statically has no apply!" % (fn_kind,))
			return fn_kind["apply"].instantiate(dest, assumptions, inputs)
		# If the input type is unknown then compile a totally generic runtime dispatch.
		# 0) Force all of the inputs to be boxed.
		fn, = ForceBoxSnippet().instantiate(dest, assumptions, [fn])
		args = [
			ForceBoxSnippet().instantiate(dest, assumptions, [arg])[0]
			for arg in args
		]
		# 1) Allocate a temporary buffer to hold the arguments contiguously.

		args_array = dest.new_tmp()
		dest.add("\t{0} = alloca %L11Obj*, i32 {1}\n".format(args_array, len(args)))
		# 2) Pack each argument into this buffer.
		for i, arg in enumerate(args):
			arg_insert_ptr = dest.new_tmp()
			dest.add("\t{0} = getelementptr %L11Obj*, %L11Obj** {1}, i32 {2}\n".format(
				arg_insert_ptr, args_array, i
			))
			dest.add("\tstore %L11Obj* {0}, %L11Obj** {1}\n".format(arg, arg_insert_ptr))
		# 3) Do the call.
		result = dest.new_tmp()
		dest.add("\t{0} = call %L11Obj* @obj_apply(%L11Obj* {1}, i32 {2}, %L11Obj** {3})\n".format(
			result, fn, len(args), args_array
		))
		return [result]

class IncRefSnippet(Snippet):
	def instantiate(self, dest, assumptions, inputs):
		obj, = inputs
		dest.add("\tcall void @obj_inc_ref(%L11Obj* {0})\n".format(obj))

class DecRefSnippet(Snippet):
	def instantiate(self, dest, assumptions, inputs):
		obj, = inputs
		dest.add("\tcall void @obj_dec_ref(%L11Obj* {0})\n".format(obj))

class AllocObjectSnippet(Snippet):
	def __init__(self, kind):
		assert isinstance(kind, Kind)
		self.kind = kind

	def instantiate(self, dest, assumptions, inputs):
		assert not inputs
		raw_ptr, result = dest.new_tmp(count=2)
		dest.add("\t{0} = call i8* @malloc(i64 {1})\n".format(raw_ptr, self.kind.total_byte_length()))
		dest.add("\t{0} = bitcast i8* {1} to %L11Obj*\n".format(result, raw_ptr))
		ref_count_ptr, kind_ptr = dest.new_tmp(count=2)
		dest.add("\t{0} = getlementptr i64, %L11Obj* {1}, i32 0, i32 0\n".format(ref_count_ptr, result))
		dest.add("\tstore i64* {0}, i64 1\n".format(ref_count_ptr))
		dest.add("\t{0} = getlementptr i64, %L11Obj* {1}, i32 0, i32 0\n".format(kind_ptr, result))
		dest.add("\tstore i64* {0}, i64 {1}\n".format(kind_ptr, self.kind.kind_number))
		# Add our typing assumption.
		assumptions.set_kind(result, self.kind)
		return result,

class FunctionSnippet(Snippet):
	def __init__(self, f):
		self.f = f

	def instantiate(self, dest, assumptions, inputs):
		return self.f(dest, assumptions, inputs)

class StaticTypeAssertSnippet(Snippet):
	def __init__(self, ty):
		self.ty = ty

	def instantiate(self, dest, assumptions, inputs):
		input_obj, = inputs
		assert assumptions.get_type(input_obj) == self.ty, "Static type assert failure!"
		return []

class KindAssertSnippet(Snippet):
	def __init__(self, kind):
		assert isinstance(kind, Kind)
		self.kind = kind

	def instantiate(self, dest, assumptions, inputs):
		input_obj, = inputs
		boxed_obj, = ForceBoxSnippet().instantiate(dest, assumptions, [input_obj])
		# Check if we already have a typing for the input.
		if assumptions.has_known_kind(boxed_obj):
			context_kind = assumptions.get_kind(boxed_obj)
			if self.kind == context_kind:
				# We statically know that the type checking will pass!
				return [boxed_obj]
			else:
				# We statically know that the type checking will fail!
				raise ValueError("Static type assert failure! %r != %r" % (self.kind, context_kind))
		# If we don't have static type information then compile in a runtime check.
		# 1) Get a pointer to the kind field.
		ptr_tmp = dest.new_tmp()
		dest.add("\t{0} = getelementptr i64*, %L11Obj* {1}, i32 0, i32 0\n".format(ptr_tmp, boxed_obj))
		# 2) Load the kind.
		kind_tmp = dest.new_tmp()
		dest.add("\t{0} = load i64, i64* {1}\n".format(kind_tmp, ptr_tmp))
		# 3) Compare the kind, and if it's not what we expected then crash.
		flag_tmp = dest.new_tmp()
		dest.add("\t{0} = icmp eq i64 {1}, i64 {2}\n".format(
			flag_tmp, kind_tmp, self.kind.kind_number
		))
		# 4) Branch on failure.
		good_label = dest.new_label()
		bad_label = dest.new_label()
		dest.add("\tbr i1 {0}, label {1}, label {2}\n".format(
			flag_tmp, good_label, bad_label
		))
		dest.add("{0}:\n".format(bad_label))
		error_ptr = dest.get_string_ptr("Type error!")
		dest.add("\tcall void @l11_panic(i8* {0})\n".format(error_ptr))
		# This is now dead code.
		dest.add("\tret %L11Obj* undef\n")
		dest.add("{0}:\n".format(good_label))
		# Add the new typing knowledge to our context.
		assumptions.set_kind(boxed_obj, self.kind)
		return [boxed_obj]

class FormatSnippet(Snippet):
	def __init__(self, input_count, output_count, ir, tmps=0):
		self.input_count = input_count
		self.output_count = output_count
		self.ir = ir
		self.tmps = tmps

	def instantiate(self, dest, assumptions, inputs):
		assert len(inputs) == self.input_count
		outputs = dest.new_tmp(count=self.output_count)
		kwargs = {}
		for i, input_var in enumerate(inputs):
			kwargs["in{0}".format(i)] = input_var
		for i, output_var in enumerate(outputs):
			kwargs["out{0}".format(i)] = output_var
		for i in xrange(self.tmps):
			kwargs["tmp{0}".format(i)] = dest.new_tmp()
		dest.add(self.ir.format(**kwargs))
		return outputs

class DebugSnippet(Snippet):
	def instantiate(self, dest, assumptions, inputs):
		print dest.format()
		print "^^^ Debug called on:", inputs, "with assumptions:"
		pprint.pprint(assumptions.gamma)
		return []

class OffsetSnippetsDryer:
	def __init__(self, byte_offset, ty, kind=None):
		assert isinstance(byte_offset, int)
		assert isinstance(ty, ValueType)
		self.byte_offset = byte_offset
		self.ty = ty
		self.kind = kind

	def compute_field_pointer(self, dest, obj):
		final_type = value_type_to_llvm_type[self.ty]
		byte_ptr, offset_byte_ptr, final_ptr = dest.new_tmp(count=3)
		dest.add("\t{0} = bitcast %L11Obj* {1} to i8*\n".format(byte_ptr, obj))
		dest.add("\t{0} = getelementptr i8, i8* {1}, i32 {2}\n".format(offset_byte_ptr, byte_ptr, self.byte_offset))
		dest.add("\t{0} = bitcast i8* {1} to {2}*\n".format(final_ptr, offset_byte_ptr, final_type))
		return final_type, final_ptr

class LoadOffsetSnippet(Snippet, OffsetSnippetsDryer):
	def instantiate(self, dest, assumptions, inputs):
		input_obj, = inputs
		assert assumptions.is_L11Obj(input_obj)
		final_type, final_ptr = self.compute_field_pointer(dest, input_obj)
		result = dest.new_tmp()
		dest.add("\t{0} = load {1}* {2}\n".format(result, final_type, final_ptr))
		# XXX: If I clean up the set_kind/set_type thing then fix this up here.
		if self.kind != None:
			assumptions.set_kind(result, self.kind)
		else:
			assumptions.set_type(result, self.ty)
		return result,

class StoreOffsetSnippet(Snippet, OffsetSnippetsDryer):
	def __init__(self, byte_offset, ty, kind=None):
		assert isinstance(byte_offset, int)
		assert isinstance(ty, ValueType)
		self.byte_offset = byte_offset
		self.ty = ty
		self.kind = kind

	def instantiate(self, dest, assumptions, inputs):
		dest_obj, obj_to_store = inputs
		# TODO: Think carefully about the safety and protocols we want here.
		assert assumptions.is_L11Obj(dest_obj)
		final_type, final_ptr = self.compute_field_pointer(dest, dest_obj)
		dest.add("\tstore {0} {1}, {0}* {2}\n".format(
			final_type, obj_to_store, final_ptr
		))
		return []

class ForceBoxSnippet(Snippet):
	def instantiate(self, dest, assumptions, inputs):
		input_obj, = inputs
		# If the object is known to already be boxed, then just return it unmodified.
		if assumptions.is_L11Obj(input_obj):
			return [input_obj]
		# If the object is known to be unboxed then lookup a conversion.
		value_type = assumptions.get_type(input_obj)
		return boxify_table[value_type].instantiate(dest, assumptions, inputs)

def initialize():
	global llvm, kind_table, boxify_table
	llvmlite.binding.initialize()
	llvmlite.binding.initialize_native_target()
	llvmlite.binding.initialize_native_asmprinter()

	# Load up the runtime interface.
	llvm = LLVM()
	llvmlite.binding.load_library_permanently(runtime.dll_path)
	with open("interface_runtime.ll") as f:
		prelude_ir = f.read()
	llvm.add_to_prelude(prelude_ir)

	kind_table = KindTable()
	boxify_table = {}

	jitstdlib.populate()

