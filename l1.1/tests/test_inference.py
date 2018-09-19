#!/usr/bin/python

import unittest
from inference import *

class Tests(unittest.TestCase):
	def setUp(self):
		self.a = MonoType("var", "a")
		self.b = MonoType("var", "b")
		self.c = MonoType("var", "c")
		self.t_int = MonoType("link", [], link_name="int")
		self.t_bool = MonoType("link", [], link_name="bool")

	def test_unification(self):
		"""Make sure that unification actually unifies types."""
		inf = Inference()
		# Before unification the two type variables need not be equal.
		self.assertFalse(inf.unification_context.must_equal(self.a, self.b))
		inf.unification_context.equate(self.a, self.b)
		# After unification the two type variables must be equal.
		self.assertTrue(inf.unification_context.must_equal(self.a, self.b))

	def test_alpha_canonicalization(self):
		"""Make sure that a test type unifies with its canonicalization."""
		t = MonoType("link", [
			MonoType("var", "a"),
			MonoType("link", [
				MonoType("var", "b"),
				MonoType("var", "a"),
			], link_name="fun"),
		], link_name="fun")
		alpha_canon = alpha_canonicalize(t)
		double_alpha_canon = alpha_canonicalize(alpha_canon)
		# Demand idempotency of alpha canonicalization, at least at this one type.
		self.assertEqual(alpha_canon, double_alpha_canon)
		# Demand that the two types unify.
		inf = Inference()
		inf.unification_context.equate(t, alpha_canon)
		self.assertEqual(
			inf.unification_context.most_specific_type(t),
			inf.unification_context.most_specific_type(alpha_canon),
		)

	def test_expr1(self):
		"""Test type inference on a simple expression."""
		inf = Inference()
		# Encode the expression:
		#   (\x -> x)(\x -> \y -> x)
		expr = Expr("app", [
			Expr("abs", [
				Expr("var", "x"),
				Expr("var", "x"),
			]),
			Expr("abs", [
				Expr("var", "x"),
				Expr("abs", [
					Expr("var", "y"),
					Expr("var", "x"),
				]),
			]),
		])
		# This should yield the type: a -> b -> a.
		expected_type = MonoType("link", [
			MonoType("var", "a"),
			MonoType("link", [
				MonoType("var", "b"),
				MonoType("var", "a"),
			], link_name="fun"),
		], link_name="fun")
		# Do type inference.
		final_type = inf.J({}, expr)
		final_type = inf.unification_context.most_specific_type(final_type)
		self.assertEqual(
			alpha_canonicalize(final_type),
			alpha_canonicalize(expected_type),
		)

	def test_let_polymorphism(self):
		"""Test that let-polymorphism is functioning within a single inference."""
		inf = Inference()
		# Encode the expression:
		#   let inner = (\x -> \y -> (x y)) in
		#   let id = (\x -> x) in (id id)(inner)
		inner_func = Expr("abs", [
			Expr("var", "x"),
			Expr("abs", [
				Expr("var", "y"),
				Expr("app", [
					Expr("var", "x"),
					Expr("var", "y"),
				]),
			]),
		])
		id_func = Expr("abs", [
			Expr("var", "z"),
			Expr("var", "z"),
		])
		expr = Expr("let", [
			Expr("var", "inner"),
			inner_func,
			Expr("let", [
				Expr("var", "id"),
				id_func,
				Expr("app", [
					Expr("app", [
						Expr("var", "id"),
						Expr("var", "id"),
					]),
					Expr("var", "inner"),
				]),
			]),
		])
		# This should yield the type: (a - > b) -> a -> b.
		expected_type = MonoType("link", [
			MonoType("link", [
				MonoType("var", "a"),
				MonoType("var", "b"),
			], link_name="fun"),
			MonoType("link", [
				MonoType("var", "a"),
				MonoType("var", "b"),
			], link_name="fun"),
		], link_name="fun")
		# Do type inference.
		final_type = inf.J({}, expr)
		final_type = inf.unification_context.most_specific_type(final_type)
		self.assertEqual(
			alpha_canonicalize(final_type),
			alpha_canonicalize(expected_type),
		)

	def test_environment(self):
		"""Test that typing environments can be read by variables."""
		inf = Inference()
		# Encode the expression:
		#   dual \x -> (dual x)
		# where dual : forall a b, (a -> b) -> b -> a
		expr = Expr("app", [
			Expr("var", "dual"),
			Expr("abs", [
				Expr("var", "x"),
				Expr("app", [
					Expr("var", "dual"),
					Expr("var", "x"),
				]),
			]),
		])
		dual_type = PolyType(
			set([MonoType("var", "a"), MonoType("var", "b")]),
			MonoType("link", [
				MonoType("link", [
					MonoType("var", "a"),
					MonoType("var", "b"),
				], link_name="fun"),
				MonoType("link", [
					MonoType("var", "b"),
					MonoType("var", "a"),
				], link_name="fun"),
			], link_name="fun"),
		)
		gamma = {Expr("var", "dual"): dual_type}
		# This should yield type: (a -> b) -> b -> a, the same as dual's monotype.
		expected_type = dual_type.mono
		# Do type inference.
		final_type = inf.J(gamma, expr)
		final_type = inf.unification_context.most_specific_type(final_type)
		self.assertEqual(
			alpha_canonicalize(final_type),
			alpha_canonicalize(expected_type),
		)

if __name__ == "__main__":
	unittest.main()

