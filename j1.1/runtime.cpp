// l1.1 runtime

#include <iostream>
#include "runtime.h"

extern "C" void obj_dec_ref(L11Obj* obj) {
	obj->ref_count--;
	if (obj->ref_count <= 0) {
		if (obj->ref_count < 0)
			l11_panic("Negative reference count!");
		KindTable* kind_table = global_kind_table.at(obj->kind).get();
		auto destructor = kind_table->destructor;
		if (destructor != nullptr)
			destructor(obj);
	}
}

extern "C" void obj_inc_ref(L11Obj* obj) {
	obj->ref_count++;
}

extern "C" L11Obj* obj_lookup(L11Obj* obj, const char* attribute_name, uint64_t attribute_name_len) {
	KindTable* kind_table = global_kind_table.at(obj->kind).get();
	std::string attribute(attribute_name, attribute_name_len);
	L11Obj* result_obj = kind_table->member_table.at(attribute);
	obj_inc_ref(result_obj);
	return result_obj;
}

extern "C" L11Obj* obj_apply(L11Obj* obj, int arg_count, L11Obj** arguments) {
	KindTable* kind_table = global_kind_table.at(obj->kind).get();
	return kind_table->apply(obj, arg_count, arguments);
}

extern "C" void l11_new_kind(Kind new_kind) {
	global_kind_table.insert(std::make_pair(
		new_kind,
		std::make_unique<KindTable>()
	));
}

extern "C" void l11_kind_set_destructor(Kind kind, void (*destructor)(L11Obj* self)) {
	KindTable* kind_table = global_kind_table.at(kind).get();
	kind_table->destructor = destructor;
}

extern "C" void l11_kind_set_apply(Kind kind, L11Obj* (*apply)(L11Obj* self, int arg_count, L11Obj** arguments)) {
	KindTable* kind_table = global_kind_table.at(kind).get();
	kind_table->apply = apply;
}

extern "C" void l11_kind_set_member(Kind kind, const char* attribute_name, uint64_t attribute_name_len, L11Obj* member) {
	KindTable* kind_table = global_kind_table.at(kind).get();
	std::string attribute(attribute_name, attribute_name_len);
	kind_table->member_table.insert(std::make_pair(
		attribute,
		member
	));
	obj_inc_ref(member);
}

extern "C" void l11_panic(const char* error_message) {
	std::cerr << "Panic: " << error_message << std::endl;
	std::abort();
}

extern "C" void debug_obj_summary(L11Obj* obj) {
	std::cout << "Object: " << obj << " with ref=" << obj->ref_count << " kind=" << obj->kind << std::endl;
}

extern "C" void* debug_malloc(uint64_t bytes) {
	return static_cast<void*>(new uint8_t[bytes]);
}

extern "C" void debug_free(void* ptr) {
	delete static_cast<uint8_t*>(ptr);
}

extern "C" void debug_destructor(L11Obj* self) {
	std::cout << "Debug destructor called on " << self << std::endl;
	delete reinterpret_cast<uint8_t*>(self);
}

extern "C" L11Obj* debug_apply(L11Obj* self, int arg_count, L11Obj** arguments) {
	std::cout << "Debug apply called on " << self << " with " << arg_count << " arguments." << std::endl;
	for (int i = 0; i < arg_count; i++)
		std::cout << "  Arg: " << arguments[i] << " ref=" << arguments[i]->ref_count << " kind=" << arguments[i]->kind << std::endl;
	// Increment the self reference, to obey our protocol.
	obj_inc_ref(self);
	return self;
}

extern "C" void debug_print_num(int64_t x) {
	std::cout << "Debug number: " << x << std::endl;
}

