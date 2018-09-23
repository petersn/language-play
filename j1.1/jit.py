#!/usr/bin/python

import jitcore
import jitstdlib
import runtime

def simple(snippet, args):
	dest = jitcore.IRDestination()
	assumptions = jitcore.AssumptionContext()
	snippet.instantiate(dest, assumptions, args)
	print dest.format()

if __name__ == "__main__":
	jitcore.initialize()

	dest = jitcore.IRDestination()
	assumptions = jitcore.AssumptionContext()
	assumptions["%a"] = jitcore.Info(jitcore.ValueType.UNBOXED_INT)
	snippet = jitcore.kind_table["int"]["__add__"]
	snippet.instantiate(dest, assumptions, ["%a", "%b"])
	jitcore.ApplySnippet().instantiate(dest, assumptions, ["%a", "%b"])
	print dest.format()

#	simple(jitcore.kind_table["int"]["__add__"], ["a", "b"])

if __name__ == "__main__" and False:
	jitcore.initialize()
	jitcore.kind_table.new_kind("nil")
#	nil_print = jitcore.FunctionIRBuilder("nil_print", [])
#	nil_print.finalize()
#	jitcore.kind_table["nil"]["print"] = nil_print

	assumptions = jitcore.AssumptionContext()
	dest = jitcore.IRDestination()

	basic = jitcore.FormatSnippet(2, 2, """
		Do some basic manipulations on {in0} and {in1} over to:
		The results {out0} and {out1} again {in0}
""")

	seq = jitcore.SequenceSnippet(2)
	x, y = seq.get_inputs()
	result, = seq(1, jitcore.ApplySnippet(), x, y, y)
	result2, result3 = seq(2, basic, x, y)
	seq(0, jitcore.KindAssertSnippet(jitcore.kind_table["nil"]), result)
	final, = seq(1, jitcore.ApplySnippet(), result, x, y)
	seq(0, jitcore.DebugSnippet())
	seq.set_outputs([x, result, final])

#	applysnippet = jitcore.ApplySnippet()
#	result = applysnippet.instantiate(dest, assumptions, ["%fn", "%arg1", "%arg2"])

	seq.instantiate(dest, assumptions, ["%x", "%y"])

