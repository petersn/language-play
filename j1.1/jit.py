#!/usr/bin/python

import jitcore
import jitllvm
import runtime

if __name__ == "__main__":
	snippet = jitcore.MethodSnippet("__add__")
	f = jitllvm.Function("simpl_add", snippet, 2)
	f.compile()

exit()

if __name__ == "__main__":
	jitcore.initialize()

	dest = jitcore.IRDestination()
	assumptions = jitcore.AssumptionContext()
	assumptions["%a"] = jitcore.Info(jitcore.ValueType.UNBOXED_INT)
	assumptions["%b"] = jitcore.Info(jitcore.ValueType.UNBOXED_INT)
#	snippet = jitcore.kind_table["int"]["__add__"]
#	snippet.instantiate(dest, assumptions, ["%a", "%b"])
	result, = jitcore.MethodSnippet("__add__").instantiate(dest, assumptions, ["%a", "%b"])
	print dest.format()
	print result

#	simple(jitcore.kind_table["int"]["__add__"], ["a", "b"])

