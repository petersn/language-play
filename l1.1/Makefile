
all:
	$(MAKE) -C antlr_parser/
	$(MAKE) -C jit/

.PHONY: test
test:
	python -m unittest discover tests/

.PHONY: clean
clean:
	$(MAKE) -C antlr_parser clean

