#!/usr/bin/python

import enum
import parser

def pretty_quantified_type_params(type_params):
	assert isinstance(type_params, list)
	def pretty_type_param(type_param):
		name, constraint = type_param
		if constraint:
			constraint, = constraint
			return "%s: %s" % (name, pretty_node(constraint))
		return name
	return "<%s>" % (", ".join(
		pretty_type_param(type_param)
		for type_param in type_params
	),)

def pretty_node(node):
	assert isinstance(node, parser.Node)
	if node.name == "qualName":
		return "::".join(node.contents)
	elif node.name == "typeGeneric":
		return "%s<%s>" % (
			pretty_node(node["generic"]),
			", ".join(
				pretty_node(type_argument)
				for type_argument in node["args"]
			),
		)
	raise NotImplementedError("Cannot pretty: %r" % (node,))

class NameKind(enum.Enum):
	# The TYPE name kind is used for traits and structs.
	TYPE = 1
	# The VALUE name kind is used for variables and functions.
	VALUE = 2
	# The NAMESPACE name kind is used for namespaces themselves, and is not generally valid.
	NAMESPACE = 3

class Name:
	def __init__(self, name_kind, name):
		assert isinstance(name_kind, NameKind)
		assert isinstance(name, str)
		self.name_kind = name_kind
		self.name = name

	def key(self):
		return self.name_kind, self.name

	def __eq__(self, other):
		return isinstance(other, Name) and self.key() == other.key()

	def __hash__(self):
		return hash(self.key())

	def __repr__(self):
		return {
			NameKind.TYPE: "%",
			NameKind.VALUE: "#",
			NameKind.NAMESPACE: "@",
		}[self.name_kind] + self.name

class Thing:
	name_connective = "::"

	def __init__(self, parent, *args, **kwargs):
		self.parent = parent
		self.children = {}
		if parent != None:
			self.universe = parent.universe
		self.construct(*args, **kwargs)

	def get_name(self):
		return str(self.name)

	def get_fully_qualified_name(self):
		if self.parent is None:
			return self.get_name()
		return self.parent.get_fully_qualified_name() + self.parent.name_connective + self.get_name()

	def qualName_to_path(self, qualName):
		assert isinstance(qualName, parser.Node)
		assert qualName.name == "qualName"
		return qualName.contents

	def lookup(self, name_kind, name_path):
		obj = self
		# TODO: This isn't quite right wrt name kinds. Values are often hiding inside of types.
		# Maybe I should just totally get rid of name kinds...
		for name_str in name_path:
			obj = obj.children[Name(name_kind, name_str)]
		return obj

	def insert_thing(self, name, thing):
		assert isinstance(name, Name)
		if name in self.children:
			raise ValueError("name %s not unique" % (name,))
		self.children[name] = thing

	def insert_and_set_name(self, name_kind, name):
		assert isinstance(name, str)
		name = Name(name_kind, name)
		self.name = name
		self.parent.insert_thing(name, self)

	def print_tree(self, depth=0):
		indent = " " * (2 * depth)
		print "%s%s" % (indent, self.name)
		self.print_special(depth=depth)
		for child_name, child in self.children.iteritems():
			assert child.name == child_name
			child.print_tree(depth=depth + 1)

	def print_special(self, depth=0):
		pass

class DataTypeBlock(Thing):
	def construct(self, ast):
		self.ast = ast
		self.insert_and_set_name(NameKind.TYPE, ast["name"])
		for constructor in ast["constructors"]:
			DataConstructor(self, constructor)

class DataConstructorBlock(Thing):
	def construct(self, ast):
		self.ast = ast
		self.insert_and_set_name(NameKind.TYPE, ast["name"])

class FunctionBlock(Thing):
	def construct(self, ast):
		self.ast = ast
		self.insert_and_set_name(NameKind.VALUE, ast["name"])

class TraitBlock(Thing):
	def construct(self, ast):
		self.ast = ast
		self.insert_and_set_name(NameKind.TYPE, ast["name"])
		self.universe.add_definitions(self.ast["body"], self)

class ImplBlock(Thing):
	def construct(self, ast):
		self.ast = ast
		# Impls are handled a little specially, and are just stored unsorted.
		self.parent.impl_collection.append(self)
		self.universe.add_definitions(self.ast["body"], self)

	def __repr__(self):
		return "{impl%s %s for %s}" % (
			pretty_quantified_type_params(self.ast["quantifiedTypeParams"]),
			pretty_node(self.ast["trait"]),
			pretty_node(self.ast["forType"]),
		)

class StubBlock(Thing):
	def construct(self, ast):
		self.ast = ast
		self.insert_and_set_name(NameKind.TYPE, ast["name"])

class LetBlock(Thing):
	def construct(self, ast):
		self.ast = ast
		self.insert_and_set_name(NameKind.TYPE, ast["name"])

class Namespace(Thing):
	def construct(self, name, name_connective="::"):
		self.name = Name(NameKind.NAMESPACE, name)
		self.name_connective = name_connective
		self.impl_collection = []

	def print_special(self, depth):
		indent = " " * (2 * depth)
		print "%s Impls: %r" % (indent, self.impl_collection)

class Type:
	def __init__(self, block, arguments):
		self.block = block
		self.arguments = arguments

	def __repr__(self):
		name = self.block.get_fully_qualified_name()
		if self.arguments:
			name += "<%s>" % (", ".join(
				repr(arg) for arg in self.arguments
			))
		return name

class TypeVariable:
	def __init__(self, name):
		self.name = name

	def __eq__(self, other):
		return isinstance(other, TypeVariable) and self.name == other.name

	def __hash__(self):
		return hash(self.name)

	def __repr__(self):
		return "?%s" % (self.name,)

class Helpers:
	@staticmethod
	def extract_type(namespace, ast):
		if ast.name == "qualName":
			try:
				type_block = namespace.lookup(NameKind.TYPE, ast)
			except KeyError:
				# If we don't find a binding for the qualName and the path is of length 1, then it's a type variable.
				# First make sure the path is of length 1.
				if len(namespace.qualName_to_path(ast)) != 1:
					raise ValueError("Cannot find type reference: %r" % (ast,))
				var_name, = ast.contents
				return TypeVariable(var_name)
			assert isinstance(type_block, (TraitBlock, DataTypeBlock))
			return Type(type_block, [])
		elif ast.name == "typeGeneric":
			type_block = namespace.lookup(NameKind.TYPE, ast["generic"])
			assert isinstance(type_block, (TraitBlock, DataTypeBlock))
			return Type(type_block,	[Helpers.extract_type(namespace, arg) for arg in ast["args"]])
		raise NotImplementedError("Unhandled type expression: %r" % (ast,))

class Universe:
	def __init__(self):
		self.root_namespace = Namespace(parent=None, name="root")
		self.root_namespace.universe = self
		self.queries = []

	def add_definitions(self, definitions, namespace=None):
		# Default to our root namespace.
		namespace = namespace or self.root_namespace
		for defin in definitions:
			assert defin.name == "topLevelDef"
			defin = defin["def"]
			getattr(self, "handle_" + defin.name)(namespace, defin)

	def handle_dataDeclaration(self, namespace, defin):
		DataTypeBlock(namespace, defin)

	def handle_fnDeclaration(self, namespace, defin):
		FunctionBlock(namespace, defin)

	def handle_traitDeclaration(self, namespace, defin):
		TraitBlock(namespace, defin)

	def handle_implDeclaration(self, namespace, defin):
		ImplBlock(namespace, defin)

	def handle_parameterStub(self, namespace, defin):
		StubBlock(namespace, defin)

	def handle_letStatement(self, namespace, defin):
		LetBlock(namespace, defin)

	def handle_query(self, namespace, defin):
		self.queries.append(defin)

	def do_queries(self):
		print "=== Doing queries."
		for query in self.queries:
			assert query.name == "query"
			query = query["query"]
			getattr(self, "do_" + query.name)(query)

	def do_traitQuery(self, query):
		print "\nDoing query."#, query
		trait = Helpers.extract_type(self.root_namespace, query["trait"])
		test_type = Helpers.extract_type(self.root_namespace, query["type"])
		print "Trait:", trait
		print "Test type:", test_type
		print "Trait check:", self.check_trait(trait, test_type)

	def check_trait(self, trait, test_type, context=None):
		
		return True

if __name__ == "__main__":
	u = Universe()

