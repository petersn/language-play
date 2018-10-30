# Simple CiC implementation

## Term language

Terms are build out of the following ilks, with an example of each:

* Annotation: `(x : t)`

  Statically asserts that a given term has a given type, and also switches inference over to checking.
* SortType: `Type2`

  Represents a single universe in the naturally-indexed hierarchy of predicative type universes.
* SortProp: `Prop`

  Represents the single impredicative universe in which matches are restricted.
* Var: `abc`

  Represents a reference to either a global inductive or definition by name, or a variable bound lexically by one of: DependentProduct, Abstraction, Match (inside of a pattern's result), or Fix (bound to the recursive function name).
* DependentProduct: `(forall x : T . U)`

  Represents a dependent product type (i.e. function type).
* Abstraction: `(fun x : T . y)`

  Represents a lambda term.
* Application: `(f x)`

  Represents the application of a term that has a DependentProduct type (a function) to an argument. For example, `f` could be an Abstraction or an InductiveConstructor.
* InductiveConstructor: `@nat.S`

  Represents a reference to a particular constructor of a global inductive.
* Match: `match t as x in ((I y1) y2) return P with | (@I.foo v) => v end`

  Represents a (dependent) pattern match on a given term.
* Fix (TODO): Speculative syntax: `(fix f (x : T) : (forall y : U . B) => z)`

  Represents a structurally recursive (i.e. primitive recursive) function, via a least fixed point over a definition.
* Axiom: No syntax, can only be built via the vernacular `Axiom`, and potentially later an admit-style tactic.

  Represents an opaque non-computational term that always infers to a particular type.
* Hole: No syntax, is only used internally for representing types that have yet to be inferred, and for building unification instances.

  If I one day have a separate "core" type theory then it won't include holes.

## Inductives

Inductives can also be defined, and are always defined via the following vernacular syntax (not yet implemented):

```
Inductive example params : Ar :=
  | constructor0 : constructor0_type
  | ...
```

Here `params` consists of a sequence of zero or more Annotations, for example `(x : nat) (y : vec x)`.
The "arity" `Ar` must be nested dependent products, ultimately terminating in some sort, for example: `(forall a : T . (forall b : (f a) . Type3))`.
Each constructor's type must also be a sequence of nested dependent products, ultimately terminating in an application of the inductive to the given parameters, followed by some number of arguments sufficient to resolve all the dependent products in the arity.

For example, in the above case of `params` and `Ar` specified we would need every constructor's type to ultimately terminate in a term of the form `((((example x) y) u1) u2)` where `u1 : T` and `u2 : (f u1)`.
There are a bunch of other (mostly currently unimplemented) restrictions on the various types (e.g. positivity checking) required for soundness.

## Match

TODO: Even begin to understand the typing rules for a match. :(

## Fixpoints

The Fix term enables us to write structurally recursive functions.
TODO: Implement normalization and typing for Fix, and a checker for primitive recursion (required for soundness).

## Papers

Using the following resources:

* [Introduction to the Calculus of Inductive Constructions](https://hal.inria.fr/hal-01094195/document)
* [Simply Easy!](http://strictlypositive.org/Easy.pdf)
* [(How to implement type theory) in an hour](http://math.andrej.com/2018/08/25/how-to-implement-type-theory-in-an-hour/)
* [Bidirectional Typing Rules: A Tutorial](http://davidchristiansen.dk/tutorials/bidirectional.pdf)

## TODO

* Make it actually work, and be even remotely confident in soundness.
* Implement higher-order unification.

