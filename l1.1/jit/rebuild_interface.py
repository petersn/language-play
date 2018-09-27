#!/usr/bin/python

import re, glob, json

interface_header = """; Defines the interface to our shared object.
; AUTOMATICALLY GENERATED -- do not edit!

%L11Obj = type {
	i64, ; ref_count
	i64  ; kind
}
"""

llvm_type = {
	"void": "void",
	"L11Obj*": "%L11Obj*",
	"L11Obj**": "%L11Obj**",
	"char*": "i8*",
	"int64_t": "i64",
	"uint64_t": "i64",
	"int": "i32",
	"Kind": "i64",
	"destructor_ptr": "void (%L11Obj*)*",
	"apply_ptr": "%L11Obj* (%L11Obj*, i32, %L11Obj**)*",
	"string*": "i8*",
}

paths = glob.glob("*.cpp")
print "Source paths:", paths

declare_re = re.compile("interf:[ ]*([^( ]+) ([^(]+)[(]([^)]+)[)]")

defins = []
for path in paths:
	with open(path) as f:
		for line in f:
			m = re.search(declare_re, line)
			if not m:
				continue
			declare_return, declare_name, declare_args = m.groups()
			declare_return = declare_return.strip()
			declare_name = declare_name.strip()
			declare_args = [arg.strip() for arg in declare_args.split(",")]
			defins.append({"return": declare_return, "name": declare_name, "args": declare_args})
			print "From %s declaring: %s %s(%s)" % (path, declare_return, declare_name, ", ".join(declare_args))

print "Writing interface.json"
with open("interface.json", "w") as f:
	json.dump({"defins": defins}, f, indent=2)
	print >>f

print "Writing interface.ll"
with open("interface.ll", "w") as f:
	print >>f, interface_header
	for defin in defins:
		print >>f, "declare %s @%s(%s)" % (
			llvm_type[defin["return"]],
			defin["name"],
			", ".join(llvm_type[arg] for arg in defin["args"]),
		)
	print >>f

