// l1.1 grammar.

grammar lang;

codeBlock : statements ;

statements : statement * ;

statement
	: dataDeclaration
	| traitDeclaration
	| implDeclaration
	| fnDeclaration
	| fnStub
	| letStatement
	| parameterStub
	| query
	| reassignmentStatement
	| exprStatement
	| ifStatement
	| forStatement
	| whileStatement
	| returnStatement
	;

dataDeclaration : 'data' ident optionalTypeParameterList '{' dataConstructorList '}' ;
dataConstructorList : | dataConstructorSpec ( ',' dataConstructorSpec ) * ',' ? ;
dataConstructorSpec : ident optionalTypeList ;

// Duplication here with typeList to avoid the extra entries in the AST.
optionalTypeList : | '(' typeExpression ( ',' typeExpression ) * ',' ? ')' ;
optionalTypeParameterList : | '<' argSpec ( ',' argSpec ) * ',' ? '>' ;

traitDeclaration : 'trait' ident optionalTypeParameterList '{' codeBlock '}' ;

implDeclaration : 'impl' optionalTypeParameterList typeExpression 'for' typeExpression '{' codeBlock '}' ;

fnDeclaration : fnCore '{' codeBlock '}' ;
fnStub : fnCore ';' ;
fnCore : 'fn' ident optionalTypeParameterList '(' argList ')' optionalReturnTypeAnnot ;

optionalTypeAnnot : | typeAnnotation ;
optionalReturnTypeAnnot : | '->' typeExpression ;

typeAnnotation : ':' typeExpression ;
typeExpression : qualName | typeGeneric ;
typeGeneric : qualName '<' typeList '>' ;

argList : | argSpec ( ',' argSpec ) * ',' ? ;
argSpec : ident optionalTypeAnnot ;
typeList : | typeExpression ( ',' typeExpression ) * ',' ? ;

parameterStub : 'parameter' ident typeAnnotation ';' ;

// Various definitions specific to imperative code and expressions.

letStatement : ident optionalTypeAnnot ':=' expr ';' ;
reassignmentStatement : ident optionalTypeAnnot '=' expr ';' ;
exprStatement : expr ';' ;

ifStatement : 'if' expr '{' codeBlock '}' optionalElifStatements optionalElseStatement ;
optionalElifStatements : elifStatement * ;
elifStatement : 'elif' expr '{' codeBlock '}' ;
optionalElseStatement : | elseStatement ;
elseStatement : 'else' '{' codeBlock '}' ;

forStatement : 'for' ident 'in' expr '{' codeBlock '}' ;
whileStatement : 'while' expr '{' codeBlock '}' ;

breakStatement : 'break' ';' ;
continueStatement : 'continue' ';' ;
returnStatement : 'return' optionalExpr ';' ;

// ANTLR4 only handles left-recursive rules if they're all together as one rule, so we list everything left-recursive here.
expr : appExpr | nonAppExpr | methodCallExpr ;

appExpr
	: appExpr '(' exprList ')'
	| nonAppExpr '(' exprList ')'
	;

nonAppExpr
	: matchExpr
	| qualName
	| lambdaExpr
	| letExpr
	| literalExpr
	| '(' expr ')'
	| '{' expr '}'
	;

methodCallExpr : (appExpr | nonAppExpr) '.' ident '(' exprList ')' ;

optionalExpr : | expr ;

lambdaExpr : '|' argList '|' optionalReturnTypeAnnot expr ;

matchExpr : 'match' expr '{' matchArms '}' ;
matchArms : | matchArm ( ',' matchArm ) * ',' ? ;
matchArm : matchPattern '=>' expr ;
matchPattern : matchPrimitive | matchConstructor ;
matchConArgNameList : | matchPrimitive ( ',' matchPrimitive ) * ',' ? ;
matchPrimitive : matchHole | matchVariable ;
matchConstructor : qualName optionalMatchConArgNameList ;
optionalMatchConArgNameList : | '(' matchConArgNameList ')' ;
matchHole : '_' ;
matchVariable : ident ;

exprList : | expr ( ',' expr ) * ',' ? ;
letExpr : 'let' ident optionalTypeAnnot '=' expr 'in' expr ;

literalExpr
	: litNum
	| litString
	;

litNum : DIGIT + | DIGIT + '.' DIGIT * | '.' DIGIT + ;

litString : '"' ( stringChar | escapeSequence ) * '"' ;
 stringChar : ~( '\\' | '"' ) ;
 escapeSequence : '\\' . ;
// ['"a-zA-Z\\]

qualName : ( ident '::' ) * ident ;
ident : ID ;

// Separate query language.

query : typeQuery | traitQuery ;
typeQuery : '#queryType' '[' expr ']' ;
traitQuery : '#queryTrait' '[' typeExpression 'for' typeExpression ']' ;

// Terminal rules.

 ID : [a-zA-Z_][a-zA-Z0-9_]* ;
 DIGIT : [0-9] ;
WS : [ \r\n\t]+ -> channel(HIDDEN) ;
COMMENT : ( '//' ~[\r\n]* '\r'? '\n' ) -> skip ;
BLOCKCOMMENT : '/*' .*? '*/' -> skip ;

