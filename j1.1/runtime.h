// l1.1 runtime

#ifndef L11_RUNTIME_H
#define L11_RUNTIME_H

#include <memory>
#include <string>
#include <unordered_map>
#include <stdint.h>

typedef uint64_t Kind;

namespace BuiltinKinds {
	enum {
		KIND_NIL = 1,
		KIND_FUNCTION = 2,
	};
}

struct L11Obj {
	// ref_count is signed to detect underflows without additional logic.
	int64_t ref_count;
	Kind kind;
};

// Define structs for all the built-in kinds.

struct L11Nil : public L11Obj {
};

struct L11Function : public L11Obj {
	L11Obj* (*native_code)(L11Function* self, int arg_count, L11Obj** arguments);
};

struct KindTable {
	void (*destructor)(L11Obj* self);
	std::unordered_map<std::string, L11Obj*> member_table;
};

extern "C" void obj_dec_ref(L11Obj* obj);
extern "C" void obj_inc_ref(L11Obj* obj);
extern "C" L11Obj* obj_lookup(L11Obj* obj, const char* attribute_name, uint64_t attribute_name_len);
extern "C" L11Obj* obj_apply(L11Obj* fn_obj, int arg_count, L11Obj** arguments);
extern "C" L11Obj* obj_method_call(L11Obj* obj, const char* attribute_name, uint64_t attribute_name_len, int arg_count, L11Obj** arguments);

extern "C" void l11_new_kind(Kind new_kind);
extern "C" void l11_kind_set_destructor(Kind kind, void (*destructor)(L11Obj* self));
extern "C" void l11_kind_set_member(Kind kind, const char* attribute_name, uint64_t attribute_name_len, L11Obj* member);
extern "C" L11Function* l11_create_function_from_pointer(L11Obj* (*native_code)(L11Function* self, int arg_count, L11Obj** arguments));
extern "C" void l11_panic(const char* error_message);

// Purely for debugging; I'll probably remove these.
extern "C" void debug_obj_summary(L11Obj* obj);
extern "C" void* debug_malloc(uint64_t bytes);
extern "C" void debug_free(void* ptr);
extern "C" void debug_destructor(L11Obj* self);
extern "C" L11Obj* debug_apply(L11Obj* self, int arg_count, L11Obj** arguments);

extern "C" void debug_print_num(int64_t x);

extern L11Nil* global_nil;
std::unordered_map<Kind, std::unique_ptr<KindTable>> global_kind_table;

#endif

