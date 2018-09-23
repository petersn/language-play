#!/usr/bin/python

import os, ctypes

runtime_dir = os.path.dirname(os.path.realpath(__file__))
dll_path = os.path.join(runtime_dir, "libruntime.so")
dll = ctypes.CDLL(dll_path)

Kind = ctypes.c_ulong

class L11Obj(ctypes.Structure):
	_fields_ = [
		("ref_count", ctypes.c_long),
		("kind", Kind),
	]

L11ObjPtr = ctypes.POINTER(L11Obj)

destructor_type = ctypes.CFUNCTYPE(None, L11ObjPtr)
apply_type = ctypes.CFUNCTYPE(L11ObjPtr, L11ObjPtr, ctypes.c_int, ctypes.POINTER(L11ObjPtr))

# Unfortunately I can't figure out how to get ctypes to respect the above types, so just use void* instead... :(
destructor_type = apply_type = ctypes.c_void_p

desc = [
	("obj_dec_ref", None, [L11ObjPtr]),
	("obj_inc_ref", None, [L11ObjPtr]),
	("obj_lookup", L11ObjPtr, [L11ObjPtr, ctypes.c_char_p, ctypes.c_ulong]),
	("obj_apply", L11ObjPtr, [L11ObjPtr, ctypes.c_int, ctypes.POINTER(L11ObjPtr)]),
	("l11_new_kind", None, [Kind]),
	("l11_kind_set_destructor", None, [Kind, destructor_type]),
#	("l11_kind_set_apply", None, [Kind, apply_type]),
	("l11_kind_set_member", None, [Kind, ctypes.c_char_p, ctypes.c_ulong, L11ObjPtr]),
	("l11_panic", None, [ctypes.c_char_p]),
	("debug_obj_summary", None, [L11ObjPtr]),
	("debug_malloc", ctypes.c_void_p, [ctypes.c_ulong]),
	("debug_free", None, [ctypes.c_void_p]),
	("debug_destructor", None, [L11ObjPtr]),
	("debug_apply", None, [L11ObjPtr, ctypes.c_int, ctypes.POINTER(L11ObjPtr)]),
	("debug_print_num", None, [ctypes.c_long]),
]

for name, restype, argtypes in desc:
	f = globals()[name] = getattr(dll, name)
	f.restype = restype
	f.argtypes = argtypes

if __name__ == "__main__":
	# Make a new kind 1 with debug fields.
	l11_new_kind(1)
	l11_kind_set_destructor(1, debug_destructor)
	l11_kind_set_apply(1, debug_apply)

	# Create an L11Obj with one ref and our new kind.
	_ptr = debug_malloc(8)
	ptr = ctypes.cast(_ptr, L11ObjPtr)
	ptr.contents.ref_count = 1
	ptr.contents.kind = 1
	debug_obj_summary(ptr)

	# If x is our new object, then evaluate x(x, x)
	arg_array = (L11ObjPtr * 2)()
	arg_array[0] = ptr
	arg_array[1] = ptr
	returned_obj = obj_apply(ptr, 2, arg_array)
	# To obey our reference ownership protocol we have to decrement this reference.
	obj_dec_ref(returned_obj)

	# Remove the last reference and therefore delete.
#	print "About to free."
#	debug_obj_summary(ptr)
#	obj_dec_ref(returned_obj)

#	l11_panic("Goodbye!")

