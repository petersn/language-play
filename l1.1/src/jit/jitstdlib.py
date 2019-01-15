#!/usr/bin/python

import jitcore
import jitllvm

def make_trivial_unboxer_snippet(ty, kind):
	@jitcore.FunctionSnippet
	def force_unboxed_snippet(dest, assumptions, inputs):
		dest.add("; force unbox %s\n" % (ty,))
		x, = inputs
		# If the object is already an unboxed value of the right type then we noop.
		if assumptions[x].get_type() == ty:
			return x,
		assert assumptions[x].is_l11obj(), "Attempting to unbox something that is neither the right unboxed type nor a boxed value."
		# The object must be boxed, so let's assert the kind.
		x, = jitcore.BoxedKindAssertSnippet(kind).instantiate(dest, assumptions, [x])
		# Extract the field.
		value, = jitcore.LoadSlotSnippet(kind, "value").instantiate(dest, assumptions, [x])
		return value,
	return force_unboxed_snippet

def make_trivial_operation_snippet(arity, unboxer_snippet, result_type, ir):
	@jitcore.FunctionSnippet
	def operation_snippet(dest, assumptions, inputs):
		assert len(inputs) == arity, "Bad arity: wanted %i got %r" % (arity, inputs)
		# Unbox all the inputs.
		unboxed_inputs = [
			unboxer_snippet.instantiate(dest, assumptions, [arg])[0]
			for arg in inputs
		]
		# Instantiate the operation's IR template.
		result, = jitcore.FormatSnippet(arity, 1, ir).instantiate(dest, assumptions, unboxed_inputs)
		assumptions[result] = jitcore.Info(result_type)
		return result,
	return operation_snippet

def make_int_snippet_factory(value):
	assert isinstance(value, int)
	@jitcore.FunctionSnippet
	def snippet(dest, assumptions, inputs):
		result = dest.new_tmp()
		dest.add("\t{0} = add i64 0, {1}\n".format(result, value))
		assumptions[result] = jitcore.Info(jitcore.ValueType.UNBOXED_INT)
		return result,
	return snippet

def populate_kinds():
	# First populate the built-in kinds.
	jitcore.kind_table.new_kind("nil", kind_number=1)

	jitcore.kind_table.new_kind("function", kind_number=2)
	jitcore.kind_table["function"].add_slots([
		{
			"name": "contents",
			"llvm_type": "%L11Obj* (%L11Obj*, i32, %L11Obj**)*",
			"info": jitcore.Info(jitcore.ValueType.OPAQUE),
			"size": 8,
		},
	])

	# Add custom kinds.
	jitcore.kind_table.new_kind("int")
	jitcore.boxify_kind_table[jitcore.ValueType.UNBOXED_INT] = jitcore.kind_table["int"]
	jitcore.kind_table["int"].add_slots([
		{
			"name": "value",
			"llvm_type": "i64",
			"info": jitcore.Info(jitcore.ValueType.UNBOXED_INT),
			"size": 8,
		},
	])

	jitcore.kind_table.new_kind("bool")
	jitcore.boxify_kind_table[jitcore.ValueType.UNBOXED_BOOL] = jitcore.kind_table["bool"]
	jitcore.kind_table["bool"].add_slots([
		{
			"name": "value",
			"llvm_type": "i1",
			"info": jitcore.Info(jitcore.ValueType.UNBOXED_BOOL),
			"size": 1,
		},
	])

	jitcore.kind_table.new_kind("str")
	#jitcore.boxify_kind_table[jitcore.ValueType.UNBOXED_BOOL] = jitcore.kind_table["str"]
	jitcore.kind_table["str"].add_slots([
		# This is based off of sizeof(std::string) == 32, empirically.
		# XXX: Very fragile! Fix this horrificness.
		{
			"name": "contents",
			"llvm_type": "[32 x i8]",
			"info": jitcore.Info(jitcore.ValueType.OPAQUE),
			"size": 32,
		},
	])

def populate_methods():
	global force_unboxers
	# Make unboxers.
	force_unboxed_int_snippet = make_trivial_unboxer_snippet(
		jitcore.ValueType.UNBOXED_INT,
		jitcore.kind_table["int"],
	)
	force_unboxed_bool_snippet = make_trivial_unboxer_snippet(
		jitcore.ValueType.UNBOXED_BOOL,
		jitcore.kind_table["bool"],
	)

	@jitcore.snippet_maker
	def box_int_snippet(seq, x):
		seq(0, jitcore.FormatSnippet(0, 0, "; box int\n"))
		seq(0, jitcore.StaticTypeAssertSnippet(jitcore.ValueType.UNBOXED_INT), x)
		result, = seq(1, jitcore.AllocObjectSnippet(jitcore.kind_table["int"]))
		seq(0, jitcore.StoreSlotSnippet(jitcore.kind_table["int"], "value"), result, x)
		return result,

	jitcore.boxify_table[jitcore.ValueType.UNBOXED_INT] = box_int_snippet
	jitcore.boxify_kind_table[jitcore.ValueType.UNBOXED_INT] = jitcore.kind_table["int"]

	force_unboxers = {
		"int": force_unboxed_int_snippet,
		"bool": force_unboxed_bool_snippet,
	}

	operations = [
#		("nil", "__str__",  2, jitcore.ValueType.UNBOXED_INT,  "\t{out0} = add i64 {in0}, {in1}\n"),

		("int", "__add__",  2, jitcore.ValueType.UNBOXED_INT,  "\t{out0} = add i64 {in0}, {in1}\n"),
		("int", "__sub__",  2, jitcore.ValueType.UNBOXED_INT,  "\t{out0} = sub i64 {in0}, {in1}\n"),
		("int", "__mul__",  2, jitcore.ValueType.UNBOXED_INT,  "\t{out0} = mul i64 {in0}, {in1}\n"),
		("int", "__div__",  2, jitcore.ValueType.UNBOXED_INT,  "\t{out0} = sdiv i64 {in0}, {in1}\n"),
		("int", "__neg__",  1, jitcore.ValueType.UNBOXED_INT,  "\t{out0} = sub i64 0, {in0}\n"),
		("int", "__bool__", 1, jitcore.ValueType.UNBOXED_BOOL, "\t{out0} = icmp ne i64 {in0}, i64 0\n"),
		("int", "apply",    2, jitcore.ValueType.UNBOXED_INT, "\t{out0} = add i64 {in0}, {in1}\n"),

		("bool", "__bool__", 1, jitcore.ValueType.UNBOXED_BOOL, "\t{out0} = bitcast i1 {in0} to i1 ; intentional noop\n"),
	]

	for kind_name, operation_name, arity, result_type, ir_template in operations:
		unboxer = force_unboxers[kind_name]
		operation_snippet = make_trivial_operation_snippet(arity, unboxer, result_type, ir_template)
		function = jitllvm.Function(operation_name, operation_snippet, arity)
		jitcore.kind_table[kind_name][operation_name] = function #operation_snippet

def populate():
	populate_kinds()
	populate_methods()

