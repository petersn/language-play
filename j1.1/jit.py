#!/usr/bin/python

import jitcore
import jitstdlib
import jitllvm
import runtime
import ctypes

if __name__ == "__main__":
	jitcore.initialize()

#	snippet = jitcore.MethodSnippet("__add__")
	f = jitllvm.Function("int___add__", jitcore.kind_table["int"]["__add__"], 2)
	f.compile()
	runtime.l11_kind_set_member(jitcore.kind_table["int"].kind_number, "__add__", len("__add__"), f.function_l11obj)



	snippet = jitcore.FormatSnippet(0, 0, """
	; Raw!
	%str = alloca i8, i32 8
	%ptr.0 = getelementptr i8, i8* %str, i32 0
	store i8 33, i8* %ptr.0
	%ptr.1 = getelementptr i8, i8* %str, i32 1
	store i8 0, i8* %ptr.1
	call void @l11_panic(i8* %str)
""")

	@jitcore.FunctionSnippet
	def launch_snippet(dest, assumptions, inputs):
		dest.add("\t%x = add i64 0, 17\n")
		assumptions["%x"] = jitcore.Info(jitcore.ValueType.UNBOXED_INT)
		dest.add("\t%y = add i64 0, 34\n")
		assumptions["%y"] = jitcore.Info(jitcore.ValueType.UNBOXED_INT)
		boxed_x, = jitcore.ForceBoxSnippet().instantiate(dest, assumptions, ["%x"])
		boxed_y, = jitcore.ForceBoxSnippet().instantiate(dest, assumptions, ["%y"])
		# For testing purposes only we want to verify that dynamic dispatch via the object's kind table works!
		# We therefore prevent the optimization where MethodSnippet knows the types of the arguments statically, and just inlines __add__.
		# Therefore we drop our type knowledge of boxed_x and boxed_y so that they end up being treated as L11Objs of unknown type.
		assumptions.gamma.pop(boxed_x)
		assumptions.gamma.pop(boxed_y)
		# Now add the number into itself.
		result, = jitcore.MethodSnippet("__add__").instantiate(dest, assumptions, [boxed_x, boxed_x, boxed_y])
		result, = jitstdlib.force_unboxers["int"].instantiate(dest, assumptions, [result])
		dest.add("\tret i64 {0}\n".format(result))
		#dest.add("\t; Raw!\n")
		return []

#	@jitcore.FunctionSnippet
#	def launch_snippet(dest, assumptions, inputs):
#		dest.add("\t%x = add i64 0, 17\n")
#		assumptions["%x"] = jitcore.Info(jitcore.ValueType.UNBOXED_INT)
#		boxed_x, = jitcore.ForceBoxSnippet().instantiate(dest, assumptions, ["%x"])
#		assumptions.gamma.pop(boxed_x)
#		# Now add the number into itself.
#		result, = jitcore.MethodSnippet("to_string").instantiate(dest, assumptions, [boxed_x])
#		#dest.add("\t; Raw!\n")
#		return []

	f2 = jitllvm.RawFunction("launch", launch_snippet, 0)
	f2.compile()

	fp = ctypes.CFUNCTYPE(ctypes.c_long)(f2.function_pointer)
	print "Calling..."
	value = fp()
	print "Value:", value

if __name__ == "__main__" and False:
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

