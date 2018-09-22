#!/usr/bin/python

import jitcore

def populate():
	jitcore.kind_table.new_kind("int")
	jitcore.kind_table["int"]

	@jitcore.snippet_maker
	def box_int_snippet(seq, x):
		seq(0, jitcore.StaticTypeAssertSnippet(jitcore.ValueType.UNBOXED_INT), x)
		result, = seq(1, jitcore.AllocObjectSnippet(jitcore.kind_table["int"]))
		seq(0, jitcore.StoreOffsetSnippet(
			jitcore.l11obj_header_size + 0,
			jitcore.ValueType.UNBOXED_INT,
		), result, x)
		return result,

	jitcore.boxify_table[jitcore.ValueType.UNBOXED_INT] = box_int_snippet

	@jitcore.snippet_maker
	def int_add_snippet(seq, x, y):
		x, = seq(1, jitcore.KindAssertSnippet(jitcore.kind_table["int"]), x)
		y, = seq(1, jitcore.KindAssertSnippet(jitcore.kind_table["int"]), y)
		x_value, = seq(1, jitcore.LoadOffsetSnippet(
			jitcore.l11obj_header_size + 0,
			jitcore.ValueType.UNBOXED_INT,
		), x)
		y_value, = seq(1, jitcore.LoadOffsetSnippet(
			jitcore.l11obj_header_size + 0,
			jitcore.ValueType.UNBOXED_INT,
		), y)
		result, = seq(1, jitcore.FormatSnippet(2, 1, """
	{out0} = add i64 {in0}, {in1}
"""), x_value, y_value)
		def set_info(dest, assumptions, inputs):
			input_obj, = inputs
			assumptions.set_type(input_obj, jitcore.ValueType.UNBOXED_INT)
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

