// l1.1 runtime

#ifndef L11_RUNTIME_H
#define L11_RUNTIME_H

#include <memory>
#include <string>
#include <unordered_map>
#include <stdint.h>

typedef uint64_t Kind;

struct L11Obj {
	// ref_count is signed to detect underflows without additional logic.
	int64_t ref_count;
	Kind kind;
};

struct KindTable {
	void (*destructor)(L11Obj* self);
	L11Obj* (*apply)(L11Obj* self, int arg_count, L11Obj** arguments);
	std::unordered_map<std::string, L11Obj*> member_table;
};

extern "C" void obj_dec_ref(L11Obj* obj);
extern "C" void obj_inc_ref(L11Obj* obj);
extern "C" L11Obj* obj_lookup(L11Obj* obj, const char* attribute_name, uint64_t attribute_name_len);
extern "C" L11Obj* obj_apply(L11Obj* obj, int arg_count, L11Obj** arguments);

extern "C" void l11_new_kind(Kind new_kind);
extern "C" void l11_kind_set_destructor(Kind kind, void (*destructor)(L11Obj* self));
extern "C" void l11_kind_set_apply(Kind kind, L11Obj* (*apply)(L11Obj* self, int arg_count, L11Obj** arguments));
extern "C" void l11_kind_set_member(Kind kind, const char* attribute_name, uint64_t attribute_name_len, L11Obj* member);
extern "C" void l11_panic(const char* error_message);

// Purely for debugging; I'll probably remove these.
extern "C" void debug_obj_summary(L11Obj* obj);
extern "C" void* debug_malloc(uint64_t bytes);
extern "C" void debug_free(void* ptr);
extern "C" void debug_destructor(L11Obj* self);
extern "C" L11Obj* debug_apply(L11Obj* self, int arg_count, L11Obj** arguments);

std::unordered_map<Kind, std::unique_ptr<KindTable>> global_kind_table;

#endif

