// l1.1 grammar.

grammar lang;

main : topLevelDef * ;

topLevelDef
	: dataDeclaration
	| fnDeclaration
	;

dataDeclaration : 'data' ident '{' dataConstructorList '}' ;

dataConstructorList
	:
	| dataConstructorSpec ( ',' dataConstructorSpec ) * ',' ?
	;

dataConstructorSpec : ident optionalTypeList ;

// Duplication here with typeList to avoid the extra entries in the AST.
optionalTypeList
	:
	| ( '(' typeExpression ( ',' typeExpression ) * ',' ? ')' )
	;

fnDeclaration : 'fn' ident '(' argList ')' optionalReturnTypeAnnot '{' codeBlock '}' ;

optionalTypeAnnot
	:
	| typeAnnotation
	;

optionalReturnTypeAnnot
	:
	| '->' typeExpression
	;

typeAnnotation : ':' typeExpression ;

typeExpression
	: qualName
	| typeGeneric
	;

typeGeneric : qualName '<' typeList '>' ;

argList
	:
	| argSpec ( ',' argSpec ) * ',' ?
	;

argSpec : ident optionalTypeAnnot ;

typeList
	:
	| typeExpression ( ',' typeExpression ) * ',' ?
	;

codeBlock : statement * ;

statement
	: letStatement
	| exprStatement
	;

letStatement : 'let' qualName '=' expr ';' ;

exprStatement : expr ;

// ANTLR4 only handles left-recursive rules if they're all together as one rule, so we list everything left-recursive here.
expr
	: appExpr
	| nonAppExpr
	;

appExpr
	: appExpr '(' exprList ')'
	| nonAppExpr '(' exprList ')'
	;

nonAppExpr
	: matchExpr
	| qualName
	| lambdaExpr
	| letExpr
	| '(' expr ')'
	| '{' expr '}'
	;

lambdaExpr : '|' argList '|' optionalReturnTypeAnnot expr ;

matchExpr : 'match' expr '{' matchArms '}' ;

matchArms
	:
	| matchArm ( ',' matchArm ) * ',' ?
	;

matchArm : matchPattern '=>' expr ;

matchPattern
	: matchPrimitive
	| matchConstructor
	;

matchConArgNameList
	:
	| matchPrimitive ( ',' matchPrimitive ) * ',' ?
	;

matchPrimitive
	: matchHole
	| matchVariable
	;

matchConstructor : qualName optionalMatchConArgNameList ;

optionalMatchConArgNameList
	:
	| '(' matchConArgNameList ')'
	;

matchHole : '_' ;

matchVariable : ident ;

exprList
	:
	| expr ( ',' expr ) * ',' ?
	;

letExpr : 'let' qualName '=' expr 'in' expr ;

qualName : ( ident '::' ) * ident ;

ident : ID ;

// Terminal rules.

ID : [a-zA-Z0-9_]+ ;
WS : [ \r\n\t]+ -> channel(HIDDEN) ;
COMMENT : ( '//' ~[\r\n]* '\r'? '\n' ) -> skip ;
BLOCKCOMMENT : '/*' .*? '*/' -> skip ;

