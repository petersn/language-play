#!/usr/bin/python

import argparse
import parsing

class Context:
	def __init__(self, mappings, parent=None):
		self.mappings = mappings
		self.parent = parent

	def __contains__(self, key):
		return key in self.mappings or (parent and key in parent)

	def __getitem__(self, key):
		if key in self.mappings:
			return self.mappings[key]
		if self.parent:
			return self.parent[key]
		raise KeyError(key)

	def __setitem__(self, key, value):
		self.mappings[key] = value

class DataType(Context):
	def __init__(self, defin, parent):
		Context.__init__(self, {}, parent=parent)
		self.name = defin["name"]
		for constructor in defin["constructors"]:
			self[constructor["name"]] = constructor

class Datum:
	def __init__(self, ty, fields):
		self.ty = ty
		self.fields = fields

	def __repr__(self):
		return "<%s%s>" % (
			self.ty["name"],
			"".join([" " + repr(i) for i in self.fields]),
		)

class Evaluator:
	def __init__(self):
		self.global_context = Context({})

	def add_definition(self, defin):
		kind = defin.name
		if kind == "dataDeclaration":
			self.global_context[defin["name"]] = DataType(defin, self.global_context)
		elif kind == "fnDeclaration":
			self.global_context[defin["name"]] = defin
		else:
			raise NotImplementedError("Unhandled top level definition: %r" % (defin,))

	def evaluate(self, expr, context):
		kind = expr.name
		if kind == "appExpr":
			fn = self.evaluate(expr["fn"], context)
			args = [self.evaluate(arg, context) for arg in expr["args"]]
			return self.perform_call(fn, args)
		elif kind == "qualName":
			return self.lookup(expr, context)
		elif kind == "letExpr":
			name, = expr["name"].contents
			context[name] = self.evaluate(expr["expr1"], context)
			return self.evaluate(expr["expr2"], context)
		elif kind == "matchExpr":
			matchee = self.evaluate(expr["matchee"], context)
			for arm in expr["arms"]:
				match_context = self.produce_match_context(matchee, arm["pattern"], context)
				if match_context != None:
					return self.evaluate(arm["result"], match_context)
			raise RuntimeError("Non-exhaustive pattern match!")
		raise NotImplementedError("Unhandled case: %r" % (kind,))

	def run_statements(self, statements, context):
		return_value = None
		for statement in statements:
			kind = statement.name
			if kind == "letStatement":
				name, = statement["name"].contents
				context[name] = self.evaluate(statement["expr"], context)
			elif kind == "exprStatement":
				return_value = self.evaluate(statement["expr"], context)
			else:
				raise NotImplementedError("Unhandled statement: %r" % (statement,))
		if return_value is None:
			raise RuntimeError("Failure to return value!")
		return return_value

	def produce_match_context(self, matchee, pattern, context):
		match_context = Context({}, parent=context)
		if pattern.name == "matchConstructor":
			# Look up the original constructor.
			original_constructor = self.lookup(pattern["name"], context)
			# Check if we match the original constructor.
			if matchee.ty != original_constructor:
				return
			# Make sure we have the right number of variables.
			if len(original_constructor["fields"]) != len(pattern["fieldNames"]):
				raise RuntimeError("Bad number of pattern variables in match arm.")
			# Fill in our new context.
			assert len(pattern["fieldNames"]) == len(matchee.fields)
			for field_name, value in zip(pattern["fieldNames"], matchee.fields):
				if field_name.name == "matchHole":
					pass
				elif field_name.name == "matchVariable":
					match_context[field_name["name"]] = value
				else:
					raise NotImplementedError("Unhandled case: %r" % (field_name,))
			return match_context
		elif pattern.name == "matchHole":
			# Always match!
			return match_context
		else:
			raise NotImplementedError("Unhandled case: %r" % (pattern,))

	def lookup(self, qual_name, context):
		for name in qual_name.contents:
			assert isinstance(name, str) # TODO: Unicode.
			context = context[name]
		return context

	def perform_call(self, fn, args):
		if fn.name == "fnDeclaration":
			if len(args) != len(fn["args"]):
				raise RuntimeError("Argument count mismatch: %s expected %i, got %i." % (fn["name"], len(fn["args"]), len(args)))
			scope_context = Context({}, parent=self.global_context)
			for (arg_name, arg_type), arg_value in zip(fn["args"], args):
				scope_context[arg_name] = arg_value
			return self.run_statements(fn["code"], scope_context)
		elif fn.name == "dataConstructorSpec":
			if len(args) != len(fn["fields"]):
				raise RuntimeError("Constructor argument count mismatch: expected %i, got %i." % (len(fn["fields"]), len(args)))
			return Datum(fn, args)
		raise RuntimeError("Not callable: %r" % (fn,))

if __name__ == "__main__":
	p = argparse.ArgumentParser()
	p.add_argument("source")
	args = p.parse_args()

	with open(args.source) as f:
		source = f.read()

	ast = parsing.parse(source)

	import core
	u = core.Universe()
	u.add_definitions(ast)
	u.root_namespace.print_tree()
	u.do_queries()

	exit()

	print "Parsed"

	ev = Evaluator()
	for top_level_def in ast:
		ev.add_definition(top_level_def["def"])

	main_call = parsing.parse("main()", kind="expr")
	result = ev.evaluate(main_call, context=ev.global_context)

	print "Final result:", result

