# Simple CiC implementation

Simple implementation of a Calculus of Inductive Constructions based type-checker using bidirectional type-checking.

## Term language

Terms are build out of the following 13 ilks, with an example of each:

* SortType: `Type2`

  Represents a single universe in the naturally-indexed hierarchy of predicative type universes.
* SortProp: `Prop`

  Represents the single impredicative universe in which matches are restricted.
* Var: `abc`

  Represents a reference to either a global inductive or definition by name, or a variable bound lexically by one of: DependentProduct, Abstraction, Match (inside of a pattern's result), or Fix (bound to the recursive function name).
* DependentProduct: `forall x : T, U`

  Represents a dependent product type (i.e. function type).
* Abstraction: `fun x : T => y`

  Represents a lambda term.
* Application: `f x`

  Represents the application of a term that has a DependentProduct type (a function) to an argument. For example, `f` could be an Abstraction, InductiveRef, or ConstructorRef.
* InductiveRef: `nat`

  Represents a reference to a particular global inductive.
  This term ilk never occurs in the desugarer's output; it only occurs in the context binding an inductive's name to a ref to the given inductive, so that Vars can resolve to when invoking infer/check/normalize.
  That is to say, if you write `nat` in your code it will become a Var which will resolve to an InductiveRef later.
* ConstructorRef: `nat::S`

  Represents a reference to a particular constructor of a particular global inductive.
  Unlike an InductiveRef this ilk is actually separate syntax and is resolved as such by the parsing/desugaring stage.
* Match: `match t ~ as x in I y1 y2 return P with I::foo a => a | I::bar a b => b end`

  Represents a (dependent) pattern match on a given term.
  For a basic match use the syntax `match t with ... end`.
  If you need to specify any of the `as`, `in`, or `return` extensions then you must place a `~` after the matchand, as shown above.
* Fix: `fix F (x : T) : (forall y : U, B) := z`

  Represents a structurally recursive (i.e. primitive recursive) function, via a least fixed point over a definition.
* Annotation: `(x %% t)`

  Statically asserts that a given term has a given type, and also switches inference over to checking.
  The syntax is a little idiosyncratic compared to the obvious `(x : t)` syntax one might expect because I'm trying to make sure that I don't accidentally introduce ambiguity into my grammar and mess myself up during development.
* Axiom: No syntax, can only be built via the vernacular `Axiom`, and potentially later an admit-style tactic.

  Represents an opaque non-computational term that always infers to a particular type.
* Hole: No syntax, is only used internally for representing types that have yet to be inferred, and for building unification instances.

  If I one day have a separate "core" type theory then it won't include holes.

It might seem that I'm missing let-in, but I think that let-in can be implemented as sugar.
In Hindley-Milner let-in is critical because in `let x := y in z` we derive a polytype for `x`, and therefore `x` can be used polymorphically in `z` (so called "let polymorphism").
Such typing polymorphism is undecidable if we used the rewrite `let x := y in z` -> `(fun x => z) y`, and then wanted to let the lambda take a polytype.
However, in CiC HM-style polytypes don't exist, and we instead have depenently type-parameterized functions like `id : forall T : Type, T -> T`, and therefore I think the above desugaring rewrite is unproblematic?
I also don't think it's important for universe polymorphism because we can always just assign `x` a universe index that's high enough to cover every usage in `z`?

## Inductives

Inductives can also be defined, and are always defined via the following vernacular syntax:

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

Some additional resources I haven't really incorporated yet:

* [https://github.com/jozefg/higher-order-unification](https://github.com/jozefg/higher-order-unification)
* [Inductive Definitions in the System Coq: Rules and Properties](http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.32.5387&rep=rep1&type=pdf)
* [Inductive Families](http://www.cse.chalmers.se/~peterd/papers/Inductive_Families.pdf)

## TODO

* Make it actually work, and be even remotely confident in soundness.
* Implement higher-order unification.

