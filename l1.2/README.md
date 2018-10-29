# Simple CiC implementation

Terms are build out of the following ilks, with an example of each:

* Annotation: `(x : t)`
* SortType: `Type2`
* SortProp: `Prop`
* Var: `abc`
* DependentProduct: `(forall x : T . U)`
* Abstraction: `(fun x : T . y)`
* Application: `(f x)`
* InductiveConstructor: `@nat.S`
* Match: `match t as x in ((I y1) y2) return P with | (@I.foo v) => v end`
* Fix (TODO): Speculative syntax: `(fix f (x : T) : (forall y : U . B) => z)`

## Papers

Using the following resources:

* [Introduction to the Calculus of Inductive Constructions](https://hal.inria.fr/hal-01094195/document)
* [Simply Easy!](http://strictlypositive.org/Easy.pdf)
* [(How to implement type theory) in an hour](http://math.andrej.com/2018/08/25/how-to-implement-type-theory-in-an-hour/)
* [Bidirectional Typing Rules: A Tutorial](http://davidchristiansen.dk/tutorials/bidirectional.pdf)

## TODO

* Make it actually work, and be even remotely confident in soundness.
* Implement higher-order unification.

