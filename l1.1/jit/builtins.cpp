// Built-in functions.

#include "builtins.h"
#include <iostream>

// interf: void make_string(string*, char*, uint64_t)
extern "C" void make_string(std::string* dest, const char* str, uint64_t str_len) {
	*dest = std::string(str, str_len);
}

// interf: void add_strings(string*, string*, string*)
extern "C" void add_strings(std::string* dest, std::string* s1, std::string* s2) {
	*dest = *s1 + *s2;
}

// interf: void print_string(string*)
extern "C" void print_string(std::string* s) {
	std::cout << "Print: " << *s << std::endl;
}

/*
BuiltInEntry built_in_entries[] = {
	{"foo", "bar", nullptr},
};
*/

