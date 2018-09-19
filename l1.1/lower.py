#!/usr/bin/python

import enum
import parsing
import inference
import traits

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
	assert isinstance(node, parsing.Node)
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
		assert isinstance(qualName, parsing.Node)
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

	def get_all_matching_things_in_scope(self, predicate):
		if predicate(self):
			yield self
		for child in self.children.itervalues():
			# yield from
			for thing in child.get_all_matching_things_in_scope(predicate):
				yield thing

	def print_tree(self, depth=0):
		indent = " " * (2 * depth)
		print "%s%s" % (indent, self.name)
		self.print_special(depth=depth)
		for child_name, child in self.children.iteritems():
			assert child.name == child_name
			child.print_tree(depth=depth + 1)

	def print_special(self, depth=0):
		pass

# ========== Define data structures for the various AST elements =========

class DataTypeBlock(Thing):
	def construct(self, ast):
		self.ast = ast
		self.insert_and_set_name(NameKind.TYPE, ast["name"])
		for constructor in ast["constructors"]:
			DataConstructor(self, constructor)

	def extract_for_trait_solving(self, extraction_context):
		# TODO: Bounds and args not currently correctly filled in.
		data_def = traits.DataDef(
			name=self.get_name(), #self.get_fully_qualified_name(),
			args=[],
			bounds=[],
			cookie=self,
		)
		extraction_context[data_def.name] = data_def
		return data_def

class DataConstructorBlock(Thing):
	def construct(self, ast):
		self.ast = ast
		self.insert_and_set_name(NameKind.TYPE, ast["name"])

class FunctionBlock(Thing):
	def construct(self, ast):
		self.ast = ast
		self.insert_and_set_name(NameKind.VALUE, ast["name"])
		self.code = CodeBlock(self, self.ast["code"])

class TraitBlock(Thing):
	def construct(self, ast):
		self.ast = ast
		self.insert_and_set_name(NameKind.TYPE, ast["name"])
		self.universe.add_definitions(self.ast["body"], self)

	def extract_for_trait_solving(self, extraction_context):
		# TODO: Bounds and args not currently correctly filled in.
		trait_def = traits.TraitDef(
			name=self.get_name(), #self.get_fully_qualified_name(),
			args=[],
			bounds=[],
			cookie=self,
		)
		extraction_context[trait_def.name] = trait_def
		return trait_def

class ImplBlock(Thing):
	def construct(self, ast):
		self.ast = ast
		# Impls are handled a little specially, and are just stored unsorted.
		self.parent.impl_collection.append(self)
		self.universe.add_definitions(self.ast["body"], self)

	def extract_for_trait_solving(self, extraction_context):
		quantified_args = []
		bounds = []
		for var_name, var_bound in self.ast["quantifiedTypeParams"]:
			var = inference.MonoType("var", var_name)
			quantified_args.append(var)
			for bound in var_bound:
				bounds.append(traits.TypeBound(
					var,
					Helpers.extract_trait_expr(extraction_context, self.parent, bound),
				))
		return traits.Impl(
			quantified_args=quantified_args,
			bounds=bounds,
			trait_expr=Helpers.extract_trait_expr(extraction_context, self.parent, self.ast["trait"]),
			type_expr=Helpers.extract_type_expr(self.parent, self.ast["forType"]),
			cookie=self,
		)

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

class CodeBlock(Thing):
	def construct(self, ast):
		self.ast = ast

class Namespace(Thing):
	def construct(self, name, name_connective="::"):
		self.name = Name(NameKind.NAMESPACE, name)
		self.name_connective = name_connective
		self.impl_collection = []

	def print_special(self, depth):
		indent = " " * (2 * depth)
		print "%s Impls: %r" % (indent, self.impl_collection)

class Helpers:
	@staticmethod
	def extract_type_expr(namespace, ast, require_trait=False):
		required_type = {
			False: DataTypeBlock,
			True: TraitBlock,
		}[require_trait]
		if ast.name == "qualName":
			try:
				type_block = namespace.lookup(NameKind.TYPE, ast)
			except KeyError:
				# If we don't find a binding for the qualName and the path is of length 1, then it's a type variable.
				# First make sure the path is of length 1.
				if len(namespace.qualName_to_path(ast)) != 1 or require_trait:
					raise ValueError("Cannot find type reference: %r" % (ast,))
				var_name, = ast.contents
				return inference.MonoType("var", var_name)
			assert isinstance(type_block, required_type)
			# XXX: I don't like this reference of types by strings for inference...
			#link_name = type_block.get_fully_qualified_name()
			link_name = type_block.get_name()
			return inference.MonoType("link", [], link_name=link_name)
		elif ast.name == "typeGeneric":
			type_block = namespace.lookup(NameKind.TYPE, ast["generic"])
			assert isinstance(type_block, required_type)
			# XXX: ... it's also going on here.
			#link_name = type_block.get_fully_qualified_name()
			link_name = type_block.get_name()
			return inference.MonoType("link", [
				Helpers.extract_type_expr(namespace, arg)
				for arg in ast["args"]
			], link_name=link_name)
		raise NotImplementedError("Unhandled type expression: %r" % (ast,))

	@staticmethod
	def extract_trait_expr(extraction_context, namespace, ast):
		monotype = Helpers.extract_type_expr(namespace, ast, require_trait=True)
		assert monotype.kind == "link", "Currently we don't allow extracting trait exprs that are just a variable, because we don't allow the HKT that would entail."
		# Convert the outermost layer of the monotype into a trait expression.
		return traits.TraitExpr(extraction_context[monotype.link_name], monotype.contents)

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
		self.build_trait_solver()

		for query in self.queries:
			assert query.name == "query"
			query = query["query"]
			getattr(self, "do_" + query.name)(query)

	def build_trait_solver(self):
		self.trait_solver = traits.TraitSolver()

		get_blocks = lambda cls: list(self.root_namespace.get_all_matching_things_in_scope(
			lambda thing: isinstance(thing, cls),
		))

		self.extraction_context = {}

		# Add data type blocks, so they can propogate their type parameter trait bounds appropriately.
		for data_type_block in get_blocks(DataTypeBlock):
			self.trait_solver.datas.append(data_type_block.extract_for_trait_solving(self.extraction_context))

		# Add trait blocks, so they can propagate something?
		for trait_block in get_blocks(TraitBlock):
			self.trait_solver.traits.append(trait_block.extract_for_trait_solving(self.extraction_context))

		# Add impls, because they're clearly necessary!
		for impl_block in self.root_namespace.impl_collection:
			self.trait_solver.impls.append(impl_block.extract_for_trait_solving(self.extraction_context))

	def do_traitQuery(self, query):
		print "\nDoing query:", query
		trait = Helpers.extract_trait_expr(self.extraction_context, self.root_namespace, query["trait"])
		test_type = Helpers.extract_type_expr(self.root_namespace, query["type"])
		print "Trait:", trait
		print "Test type:", test_type
		result = self.trait_solver.check(traits.SolverContext(), trait, test_type)
		print "Query result:", result

if __name__ == "__main__":
	u = Universe()

