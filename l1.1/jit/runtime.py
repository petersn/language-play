#!/usr/bin/python

import os, ctypes, json

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

ctype_map = {
	"void": None,
	"L11Obj*": L11ObjPtr,
	"L11Obj**": ctypes.POINTER(L11ObjPtr),
	"char*": ctypes.c_char_p,
	"int64_t": ctypes.c_long,
	"uint64_t": ctypes.c_ulong,
	"int": ctypes.c_int,
	"Kind": ctypes.c_ulong,
	"destructor_ptr": destructor_type,
	"apply_ptr": apply_type,
	"string*": ctypes.c_void_p,
}

with open(os.path.join(runtime_dir, "interface.json")) as f:
	interface_desc = json.load(f)

for defin in interface_desc["defins"]:
	f = globals()[defin["name"]] = getattr(dll, defin["name"])
	f.restype = ctype_map[defin["return"]]
	f.argtypes = [ctype_map[arg] for arg in defin["args"]]

if __name__ == "__main__":
	print "Testing code not working right now."
	exit()

	# Make a new kind 1 with debug fields.
	l11_new_kind(1)
	l11_kind_set_destructor(1, debug_destructor)
	l11_kind_set_member(1, "__call__", len("__call__"), ctypes.cast(debug_apply, ctypes.c_void_p))

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

