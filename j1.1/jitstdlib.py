#!/usr/bin/python

import jitcore

def populate():
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

	@jitcore.FunctionSnippet
	def force_unboxed_int_snippet(dest, assumptions, inputs):
		dest.add("; force unboxed int\n")
		x, = inputs
		# If the object is already an unboxed int then we noop.
		if assumptions[x].get_type() == jitcore.ValueType.UNBOXED_INT:
			return x,
		assert assumptions[x].is_L11Obj(), "Attempting to unbox something that is neither an unboxed int nor a boxed value."
		# The object must be boxed, so let's assert the kind.
		x, = jitcore.BoxedKindAssertSnippet(jitcore.kind_table["int"]).instantiate(dest, assumptions, [x])
		# Extract the field.
		value, = jitcore.LoadSlotSnippet(jitcore.kind_table["int"], "value").instantiate(dest, assumptions, [x])
		return value,

	@jitcore.snippet_maker
	def box_int_snippet(seq, x):
		seq(0, jitcore.FormatSnippet(0, 0, "; box int\n"))
		seq(0, jitcore.StaticTypeAssertSnippet(jitcore.ValueType.UNBOXED_INT), x)
		result, = seq(1, jitcore.AllocObjectSnippet(jitcore.kind_table["int"]))
		seq(0, jitcore.StoreSlotSnippet(jitcore.kind_table["int"], "value"), result, x)
		return result,

	jitcore.boxify_table[jitcore.ValueType.UNBOXED_INT] = box_int_snippet
	jitcore.boxify_kind_table[jitcore.ValueType.UNBOXED_INT] = jitcore.kind_table["int"]

	@jitcore.snippet_maker
	def int_add_snippet(seq, x, y):
		seq(0, jitcore.FormatSnippet(0, 0, "; int add\n"))
		x_value, = seq(1, force_unboxed_int_snippet, x)
		y_value, = seq(1, force_unboxed_int_snippet, y)
#		x, = seq(1, jitcore.KindAssertSnippet(jitcore.kind_table["int"]), x)
#		y, = seq(1, jitcore.KindAssertSnippet(jitcore.kind_table["int"]), y)
#		x_value, = seq(1, jitcore.LoadSlotSnippet(
#			jitcore.kind_table["int"],
#			"value",
#		), x)
#		y_value, = seq(1, jitcore.LoadSlotSnippet(
#			jitcore.kind_table["int"],
#			"value",
#		), y)
		result, = seq(1, jitcore.FormatSnippet(2, 1, """
	{out0} = add i64 {in0}, {in1}
"""), x_value, y_value)
		def set_info(dest, assumptions, inputs):
			input_obj, = inputs
			assumptions[input_obj] = jitcore.Info(jitcore.ValueType.UNBOXED_INT)
			return []
		seq(0, jitcore.FunctionSnippet(set_info), result)
		return result,

#	int_add = jitcore.SequenceSnippet(2)
#	x, y = int_add.get_inputs()
#	int_add.add_to_sequence(jitcore.KindAssertSnippet(jitcore.kind_table["int"]), [x], 0)
#	int_add.add_to_sequence(jitcore.KindAssertSnippet(jitcore.kind_table["int"]), [y], 0)
#	result, = int_add.add_to_sequence(jitcore.FormatSnippet(2, 1, """
#	; Okay.
#	; {out0} = {in0} + {in1}
#	"""), [x, y], 1)
#	int_add.set_outputs([result])

	jitcore.kind_table["int"]["__add__"] = int_add_snippet
	jitcore.kind_table["int"]["apply"] = int_add_snippet

