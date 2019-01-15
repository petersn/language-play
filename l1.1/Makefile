
all:
	$(MAKE) -C antlr_parser/
	$(MAKE) -C src/jit/

.PHONY: test
test:
	python -m unittest discover tests/

.PHONY: clean
clean:
	$(MAKE) -C antlr_parser/ clean
	$(MAKE) -C src/jit/ clean

