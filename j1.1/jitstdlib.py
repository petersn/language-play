#!/usr/bin/python

import jitcore

def make_trivial_unboxer_snippet(ty, kind):
	@jitcore.FunctionSnippet
	def force_unboxed_snippet(dest, assumptions, inputs):
		dest.add("; force unbox %s\n" % (ty,))
		x, = inputs
		# If the object is already an unboxed value of the right type then we noop.
		if assumptions[x].get_type() == ty:
			return x,
		assert assumptions[x].is_L11Obj(), "Attempting to unbox something that is neither the right unboxed type nor a boxed value."
		# The object must be boxed, so let's assert the kind.
		x, = jitcore.BoxedKindAssertSnippet(kind).instantiate(dest, assumptions, [x])
		# Extract the field.
		value, = jitcore.LoadSlotSnippet(kind, "value").instantiate(dest, assumptions, [x])
		return value,
	return force_unboxed_snippet

def make_trivial_operation_snippet(arity, unboxer_snippet, result_type, ir):
	@jitcore.FunctionSnippet
	def operation_snippet(dest, assumptions, inputs):
		assert len(inputs) == arity, "Bad arity!"
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

def populate_kinds():
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

def populate_methods():
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
		("int", "__add__",  2, jitcore.ValueType.UNBOXED_INT,  "\t{out0} = add i64 {in0}, {in1}\n"),
		("int", "__sub__",  2, jitcore.ValueType.UNBOXED_INT,  "\t{out0} = sub i64 {in0}, {in1}\n"),
		("int", "__mul__",  2, jitcore.ValueType.UNBOXED_INT,  "\t{out0} = mul i64 {in0}, {in1}\n"),
		("int", "__div__",  2, jitcore.ValueType.UNBOXED_INT,  "\t{out0} = sdiv i64 {in0}, {in1}\n"),
		("int", "__neg__",  1, jitcore.ValueType.UNBOXED_INT,  "\t{out0} = sub i64 0, {in0}\n"),
		("int", "__bool__", 1, jitcore.ValueType.UNBOXED_BOOL, "\t{out0} = icmp ne i64 {in0}, i64 0\n"),
		("int", "apply", 2, jitcore.ValueType.UNBOXED_INT, "\t{out0} = add i64 {in0}, {in1}\n"),

		("bool", "__bool__", 1, jitcore.ValueType.UNBOXED_BOOL, "\t{out0} = bitcast i1 {in0} to i1 ; intentional noop\n"),
	]

	for kind_name, operation_name, arity, result_type, ir_template in operations:
		unboxer = force_unboxers[kind_name]
		operation_snippet = make_trivial_operation_snippet(arity, unboxer, result_type, ir_template)
		jitcore.kind_table[kind_name][operation_name] = operation_snippet

def populate():
	populate_kinds()
	populate_methods()

