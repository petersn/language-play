
CXXFLAGS=-O3 -Wall -fPIC

all: libruntime.so interface.ll interface.json

libruntime.so: runtime.o builtins.o Makefile
	$(CXX) -shared -Wl,-soname,$@ -o $@ runtime.o builtins.o

interface.ll interface.json: runtime.cpp builtins.cpp Makefile
	python rebuild_interface.py

.PHONY: clean
clean:
	rm -f libruntime.so *.o *.pyc

