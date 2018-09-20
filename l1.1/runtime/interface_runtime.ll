; Defines the interface to our shared object.

%L11Obj = type {
	i64, ; ref_count
	i64  ; kind
}

declare void @obj_dec_ref(%L11Obj*)
declare void @obj_inc_ref(%L11Obj*)
declare %L11Obj* @obj_lookup(%L11Obj*, i8*, i64)
declare %L11Obj* @obj_apply(%L11Obj*, i32, %L11Obj**)

declare void @l11_new_kind(i64)
declare void @l11_kind_set_destructor(i64, void (%L11Obj*)*)
declare void @l11_kind_set_apply(i64, %L11Obj* (%L11Obj*, i32, %L11Obj**)*)
declare void @l11_kind_set_member(i64, i8*, i64, %L11Obj*)
declare void @l11_panic(i8*)

declare void @debug_obj_summary(%L11Obj*)
declare i64 @debug_malloc(i64)
declare void @debug_free(i64)
declare void @debug_destructor(%L11Obj*)
declare %L11Obj* @debug_apply(%L11Obj*, i32, %L11Obj**)

declare void @debug_print_num(i64)

