
all:
	$(MAKE) -C antlr_parser/
	$(MAKE) -C runtime/

.PHONY: test
test:
	python -m unittest discover tests/

.PHONY: clean
clean:
	$(MAKE) -C antlr_parser clean

