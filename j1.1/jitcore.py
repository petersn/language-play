#!/usr/bin/python
"""
jit.py

Basic JIT experimentation.
"""

import os, argparse, pprint, enum, inspect, collections
import llvmlite.binding
import runtime
import jitstdlib
import jitllvm

class Kind:
	def __init__(self, name, kind_number):
		self.name = name
		self.kind_number = kind_number
		self.members = {}
		self.total_byte_length = 8 + 8 # ref_count: i64 and kind: i64
		self.slots = collections.OrderedDict()

	def add_slots(self, slots):
		for desc in slots:
			assert isinstance(desc["info"], Info)
			self.slots[desc["name"]] = {
				"llvm_type": desc["llvm_type"],
				"info": desc["info"],
				"offset": self.total_byte_length,
			}
			self.total_byte_length += desc["size"]

	def __getitem__(self, key):
		return self.members[key]

	def __setitem__(self, key, value):
#		assert isinstance(value, jitllvm.Function)
		assert isinstance(value, Snippet)
		self.members[key] = value

	def __contains__(self, key):
		return key in self.members

	def __repr__(self):
		return "<Kind %s>" % (self.name,)

class KindTable:
	def __init__(self):
		self.kind_table = {}
		# Start allocating user defined kinds at 1000, because <1000 is reserved for built-in kinds that need special runtime support.
		self.kind_number_counter = 1000

	def __getitem__(self, key):
		return self.kind_table[key]

	def __contains__(self, key):
		return key in self.kind_table

	def new_kind(self, name, kind_number=None):
		if kind_number is None:
			self.kind_number_counter += 1
			kind_number = self.kind_number_counter
		kind = self.kind_table[name] = Kind(name, kind_number)
		runtime.l11_new_kind(kind_number)
		return kind

@enum.unique
class ValueType(enum.Enum):
	L11OBJ = 1
	UNBOXED_INT = 2
	UNBOXED_BOOL = 3
	OPAQUE = 4

value_type_to_llvm_type = {
	ValueType.L11OBJ: "%L11Obj*",
	ValueType.UNBOXED_INT: "i64",
	ValueType.UNBOXED_BOOL: "i1",
}

# Our static knowledge about an identifier comes in three levels:
# 1) First, we have a "type", from ValueType.
# 2) If the type is L11OBJ then we have a "kind", which is a Kind.
# 3) If the type is anything other than L11OBJ then we may or may not have an explicit compile-time value.
# One day we'll allow compile-time values for L11OBJ, but for now I'm not dealing with that.

class Info:
	"""Info

	Represents statically known information about an LLVM variable.
	"""
	def __init__(self, ty, kind=None, value=None):
		assert isinstance(ty, ValueType)
		self.ty = ty

		# Determine our kind (if applicable) and value (if applicable).
		self.kind = self.value = None
		# 1) If we're of a fixed non L11OBJ type then we have a kind that is statically determinable.
		if self.ty != ValueType.L11OBJ:
			assert kind is None, "Don't also set kind on an Info with type != ValueTypes.L11OBJ; let the inference be automatic."
			# TODO: Maybe allow some ValueTypes other than L11OBJ to not be in boxify_kind_table?
			# One could imagine a fat pointer with additional data?
			# EDIT: I'm now allowing exactly the above TODO provisionally, via the following if.
			if self.ty in boxify_kind_table:
				self.kind = boxify_kind_table[self.ty]

		if kind != None:
			self.set_kind(kind)
		if value != None:
			self.set_value(value)

	def __repr__(self):
		return "<type=%r kind=%r value=%r>" % (self.ty, self.kind, self.value)

	def get_type(self):
		return self.ty

	def get_kind(self):
		assert self.kind != None
		return self.kind

	def set_kind(self, kind):
		assert isinstance(kind, Kind)
		# Only L11Objs can have a known kind set after initialization.
		# The rationale for this is that any other ValueType should have its kind implied completely by boxify_kind_table.
		assert self.ty == ValueType.L11OBJ
		self.kind = kind

	def get_value(self):
		assert self.value != None
		return self.value

	def set_value(self, value):
		# For now we can only have a known value if our type ISN'T ValueType.L11Obj.
		assert self.ty != ValueType.L11OBJ
		self.value = value

	def is_l11obj(self):
		return self.ty == ValueType.L11OBJ

	def has_known_kind(self):
		return self.kind != None

class AssumptionContext:
	def __init__(self):
		self.gamma = {}

	def __setitem__(self, name, info):
		assert isinstance(name, str)
		assert isinstance(info, Info)
		assert name not in self.gamma, "No reassignment of Info into a context allowed!"
		self.gamma[name] = info

	def __getitem__(self, name):
		assert isinstance(name, str)
		# Implement the defaulting assumption.
		if name not in self.gamma:
			self[name] = Info(ValueType.L11OBJ)
		return self.gamma[name]

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

class MethodSnippet(Snippet):
	def __init__(self, method_name):
		self.method_name = method_name

	def instantiate(self, dest, assumptions, inputs):
		dest.add("; method %s %s\n" % (self.method_name, inputs))
		fn = inputs[0]
		args = inputs[1:]
		# Check if we know the type of the function.
#		dest.add("; fn info: %s\n" % (assumptions[fn],))
		if assumptions[fn].has_known_kind():
			fn_kind = assumptions[fn].get_kind()
			if self.method_name not in fn_kind:
				raise ValueError("Kind %r statically has no method %s!" % (fn_kind, self.method_name))
			return fn_kind[self.method_name].instantiate(dest, assumptions, inputs)
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
		method_name_str = dest.get_string_ptr(self.method_name)
		dest.add("\t{0} = call %L11Obj* @obj_method_call(%L11Obj* {1}, i8* {2}, i64 {3}, i32 {4}, %L11Obj** {5})\n".format(
			result, fn, method_name_str, len(self.method_name), len(args), args_array
		))
		return [result]

class IncRefSnippet(Snippet):
	def instantiate(self, dest, assumptions, inputs):
		dest.add("; inc ref %s\n" % (inputs,))
		obj, = inputs
		dest.add("\tcall void @obj_inc_ref(%L11Obj* {0})\n".format(obj))

class DecRefSnippet(Snippet):
	def instantiate(self, dest, assumptions, inputs):
		dest.add("; dec ref %s\n" % (inputs,))
		obj, = inputs
		dest.add("\tcall void @obj_dec_ref(%L11Obj* {0})\n".format(obj))

class AllocObjectSnippet(Snippet):
	def __init__(self, kind):
		assert isinstance(kind, Kind)
		self.kind = kind

	def instantiate(self, dest, assumptions, inputs):
		dest.add("; alloc %s\n" % (self.kind,))
		assert not inputs
		raw_ptr, result = dest.new_tmp(count=2)
		dest.add("\t{0} = call i8* @malloc(i64 {1})\n".format(raw_ptr, self.kind.total_byte_length))
		dest.add("\t{0} = bitcast i8* {1} to %L11Obj*\n".format(result, raw_ptr))
		ref_count_ptr, kind_ptr = dest.new_tmp(count=2)
		dest.add("\t{0} = getelementptr %L11Obj, %L11Obj* {1}, i32 0, i32 0\n".format(ref_count_ptr, result))
		dest.add("\tstore i64 1, i64* {0}\n".format(ref_count_ptr))
		dest.add("\t{0} = getelementptr %L11Obj, %L11Obj* {1}, i32 0, i32 1\n".format(kind_ptr, result))
		dest.add("\tstore i64 {0}, i64* {1}\n".format(self.kind.kind_number, kind_ptr))
		# Add our typing assumption.
		assumptions[result].set_kind(self.kind)
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
		assert assumptions[input_obj].get_type() == self.ty, "Static type assert failure!"
		return []

class BoxedKindAssertSnippet(Snippet):
	def __init__(self, kind):
		assert isinstance(kind, Kind)
		self.kind = kind

	def instantiate(self, dest, assumptions, inputs):
		dest.add("; kind assert %s %s\n" % (self.kind, inputs))
		input_obj, = inputs
		boxed_obj, = ForceBoxSnippet().instantiate(dest, assumptions, [input_obj])
		# Check if we already have a typing for the input.
		if assumptions[boxed_obj].has_known_kind():
			context_kind = assumptions[boxed_obj].get_kind()
			if self.kind == context_kind:
				# We statically know that the type checking will pass!
				return boxed_obj,
			else:
				# We statically know that the type checking will fail!
				raise ValueError("Static type assert failure! %r != %r" % (self.kind, context_kind))
		# If we don't have static type information then compile in a runtime check.
		# 1) Get a pointer to the kind field.
		ptr_tmp = dest.new_tmp()
		dest.add("\t{0} = getelementptr %L11Obj, %L11Obj* {1}, i32 0, i32 1\n".format(ptr_tmp, boxed_obj))
		# 2) Load the kind.
		kind_tmp = dest.new_tmp()
		dest.add("\t{0} = load i64, i64* {1}\n".format(kind_tmp, ptr_tmp))
		# 3) Compare the kind, and if it's not what we expected then crash.
		flag_tmp = dest.new_tmp()
		dest.add("\t{0} = icmp eq i64 {1}, {2}\n".format(
			flag_tmp, kind_tmp, self.kind.kind_number
		))
		# 4) Branch on failure.
		good_label = dest.new_label()
		bad_label = dest.new_label()
		dest.add("\tbr i1 {0}, label %{1}, label %{2}\n".format(
			flag_tmp, good_label, bad_label
		))
		dest.add("{0}:\n".format(bad_label))
		error_ptr = dest.get_string_ptr("Type error!\0")
		dest.add("\tcall void @l11_panic(i8* {0})\n".format(error_ptr))
		# This is now dead code.
		dest.add("\tunreachable\n")
		dest.add("{0}:\n".format(good_label))
		# Add the new typing knowledge to our context.
		assumptions[boxed_obj].set_kind(self.kind)
		return boxed_obj,

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

class SlotSnippetsDryer:
	def __init__(self, kind, slot_name):
		assert isinstance(kind, Kind)
		assert slot_name in kind.slots
		self.kind = kind
		self.slot_name = slot_name

	def compute_field_pointer(self, dest, obj):
		slot_desc = self.kind.slots[self.slot_name]
		final_type = slot_desc["llvm_type"]
		byte_ptr, offset_byte_ptr, final_ptr = dest.new_tmp(count=3)
		dest.add("\t{0} = bitcast %L11Obj* {1} to i8*\n".format(byte_ptr, obj))
		dest.add("\t{0} = getelementptr i8, i8* {1}, i32 {2}\n".format(
			offset_byte_ptr, byte_ptr, slot_desc["offset"]
		))
		dest.add("\t{0} = bitcast i8* {1} to {2}*\n".format(final_ptr, offset_byte_ptr, final_type))
		return final_type, final_ptr

class LoadSlotSnippet(Snippet, SlotSnippetsDryer):
	def instantiate(self, dest, assumptions, inputs):
		dest.add("; load offset %s %s %s\n" % (self.kind, self.slot_name, inputs))
		input_obj, = inputs
		assert assumptions[input_obj].is_l11obj()
		final_type, final_ptr = self.compute_field_pointer(dest, input_obj)
		result = dest.new_tmp()
		dest.add("\t{0} = load {1}, {1}* {2}\n".format(result, final_type, final_ptr))
		# Save the Info that we know about the field as now applying to our loaded value.
		assumptions[result] = self.kind.slots[self.slot_name]["info"]
		return result,

class StoreSlotSnippet(Snippet, SlotSnippetsDryer):
	def instantiate(self, dest, assumptions, inputs):
		dest.add("; store offset %s %s %s\n" % (self.kind, self.slot_name, inputs))
		dest_obj, obj_to_store = inputs
		# TODO: Think carefully about the safety and protocols we want here.
		assert assumptions[dest_obj].is_l11obj()
		final_type, final_ptr = self.compute_field_pointer(dest, dest_obj)
		dest.add("\tstore {0} {1}, {0}* {2}\n".format(
			final_type, obj_to_store, final_ptr
		))
		return []

class ForceBoxSnippet(Snippet):
	def instantiate(self, dest, assumptions, inputs):
		dest.add("; force box %s\n" % (inputs,))
		input_obj, = inputs
		# If the object is known to already be boxed, then just return it unmodified.
		if assumptions[input_obj].is_l11obj():
			return input_obj,
		# If the object is known to be unboxed then lookup a conversion.
		value_type = assumptions[input_obj].get_type()
		return boxify_table[value_type].instantiate(dest, assumptions, inputs)

class InlineKindCacheSnippet(Snippet):
	def instantiate(self, dest, assumptions, inputs):
		return []

def initialize():
	global llvm, kind_table, boxify_table, boxify_kind_table
	llvmlite.binding.initialize()
	llvmlite.binding.initialize_native_target()
	llvmlite.binding.initialize_native_asmprinter()

	# Load up the runtime interface.
	llvm = jitllvm.LLVM()
	llvmlite.binding.load_library_permanently(runtime.dll_path)
	with open("interface_runtime.ll") as f:
		prelude_ir = f.read()
	llvm.add_to_prelude(prelude_ir)

	kind_table = KindTable()

	# Maps a ValueType other than ValueType.L11OBJ to a snippet that performs the boxing conversion.
	boxify_table = {}

	# Maps a ValueType other than ValueType.L11OBJ to a Kind that says what we know about the output of the boxing conversion.
	# This must be the output Kind of the corresponding boxify_table snippet!
	boxify_kind_table = {}

	jitstdlib.populate()

