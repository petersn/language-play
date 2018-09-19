#!/usr/bin/python2

import pprint
import antlr4
from antlr_parser import langLexer, langParser

s = """
data Nat {
	Z,
	S(Nat),
}

fn plus(x : Nat, y) -> Nat {
	let z = foo(x, y);
	match x {
		Nat::Z => y,
		Nat::S(x) => plus(x, Nat::S(y)),
	}
}
"""

allowed_variadic = set([
	"dataConstructorSpec",
	"matchConstructor",
])

tag_rules = {
	"codeBlock": ["statements"],
	"letStatement": ["name", "optionalTypeAnnot", "expr"],
	"reassignmentStatement": ["name", "optionalTypeAnnot", "expr"],
	"exprStatement": ["expr"],
	"ifStatement": ["condExpr", "body", "elifs", "else"],
	"elifStatement": ["condExpr", "body"],
	"elseStatement": ["body"],
	"forStatement": ["name", "expr", "body"],
	"whileStatement": ["condExpr", "body"],
	"breakStatement": [],
	"continueStatement": [],
	"returnStatement": ["optionalExpr"],
	"dataDeclaration": ["name", "typeParams", "constructors"],
	"dataConstructorSpec": ["name", "fields"],
	"traitDeclaration": ["name", "typeParams", "body"],
	"implDeclaration": ["quantifiedTypeParams", "trait", "forType", "body"],
	"fnDeclaration": ["name", "typeParams", "args", "returnType", "result"],
	"fnStub": ["name", "typeParams", "args", "returnType"],
	"parameterStub": ["name", "typeAnnot"],
	"appExpr": ["fn", "args"],
	"lambdaExpr": ["args", "returnType", "result"],
	"typeGeneric": ["generic", "args"],
	"matchArm": ["pattern", "result"],
	"matchExpr": ["matchee", "arms"],
	"matchHole": [],
	"matchVariable": ["name"],
	"matchConstructor": ["name", "fieldNames"],
	"letExpr": ["name", "optionalTypeAnnot", "expr1", "expr2"],
	"qualName": None,
	"ident": None,
	"query": ["query"],
	"typeQuery": ["expr"],
	"traitQuery": ["trait", "type"],
}

untagged_rules = set([
	"main",
	"optionalElifStatements",
	"optionalElseStatement",
	"dataConstructorList",
	"matchArms",
	"optionalMatchConArgNameList",
	"exprList",
	"typeList",
	"optionalTypeList",
	"optionalGenericParameters",
	"optionalTypeParameterList",
	"argList",
	"argSpec",
	"optionalTypeAnnot",
	"optionalReturnTypeAnnot",
	"optionalExpr",
	"statements",
])

transparent_rules = set(langParser.langParser.ruleNames) - set(tag_rules) - untagged_rules

class Node:
	def __init__(self, name, contents):
		self.name = name
		self.contents = contents

	def __getitem__(self, index):
		return self.contents[index]

	def __repr__(self):
		return "<%s %s>" % (self.name, self.contents)

class Visitor(antlr4.ParseTreeVisitor):
	def defaultResult(self):
		assert False

	def aggregateResult(self, aggregate, nextResult):
		assert False

	def collectChildren(self, node):
		l = []
		for i in xrange(node.getChildCount()):
			for v in self.visit(node.getChild(i)):
				l.append(v)
		return l

	for name in langParser.langParser.ruleNames:
		def _(name, class_locals):
			def new_method(self, node):
				if name in tag_rules:
					if tag_rules[name] is None:
						yield Node(str(name), self.collectChildren(node))
					else:
						children = self.collectChildren(node)
						if name not in allowed_variadic:
							assert len(tag_rules[name]) == len(children), "Bad lengths: %r %r" % (name, children)
						else:
							assert len(tag_rules[name]) >= len(children), "Bad variadic lengths: %r %r" % (name, children)
						yield Node(str(name), {
							k: v for k, v in zip(tag_rules[name], children)
						})
				elif name in untagged_rules:
					yield self.collectChildren(node)
				elif name in transparent_rules:
					for obj in self.collectChildren(node):
						yield obj
			upper_first = name[:1].upper() + name[1:]
			class_locals["visit" + upper_first] = new_method
		_(name, locals())
	del _

	def visitTerminal(self, node):
		# All terminals are transparent.
		return
		yield

	def visitErrorNode(self, node):
		raise RuntimeError(str(node))

	def visitIdent(self, node):
		# TODO: Remove str. For now suppress unicode like an evil person.
		yield str(node.ID().symbol.text)

def parse(s, kind="codeBlock"):
	lexer = langLexer.langLexer(antlr4.InputStream(s))
	stream = antlr4.CommonTokenStream(lexer)
	parser = langParser.langParser(stream)
	tree = getattr(parser, kind)()
	visitor = Visitor()
	result, = visitor.visit(tree)
	return result

