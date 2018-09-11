
langParser.py: lang.g4 Makefile
	antlr4 -Dlanguage=Python2 -listener -visitor lang.g4

.PHONY: clean
clean:
	rm -f *.pyc langLexer.py langLexer.tokens langParser.py lang.tokens langVisitor.py langListener.py

