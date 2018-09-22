
CXXFLAGS=-O3 -Wall -fPIC

all: libruntime.so

libruntime.so: runtime.o Makefile
	$(CXX) -shared -Wl,-soname,$@ -o $@ $<

.PHONY: clean
clean:
	rm -f libruntime.so *.o

