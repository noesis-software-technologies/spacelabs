"""Tests arithmétiques du service de calcul cardshow."""
import pytest
from decimal import Decimal

from apps.cardshow.services import calculer_tiers, parse_decimal


def test_parse_decimal_virgule():
    assert parse_decimal("12,50") == Decimal("12.50")


def test_parse_decimal_negatif():
    assert parse_decimal("-5") is None


def test_parse_decimal_invalide():
    assert parse_decimal("abc") is None


def test_parse_decimal_vide():
    assert parse_decimal("") is None


def test_calculer_tiers_basique():
    tiers = calculer_tiers(Decimal("10"), Decimal("2"))
    assert len(tiers) == 3
    # C = 12 ; PV palier 30% = 12 / 0.70 = 17.14
    t30 = tiers[0]
    assert t30["taux_marque_pct"] == 30
    assert t30["pv"] == Decimal("17.14")
    assert t30["marge"] == Decimal("5.14")
    assert t30["erreur"] is None


def test_calculer_tiers_cout_zero():
    tiers = calculer_tiers(Decimal("0"), Decimal("0"))
    for t in tiers:
        assert t["pv"] == Decimal("0.00")
        assert t["marge"] == Decimal("0.00")
        assert t["erreur"] is None


def test_calculer_tiers_palier_50():
    tiers = calculer_tiers(Decimal("5"), Decimal("5"))
    # C = 10 ; PV palier 50% = 10 / 0.50 = 20.00
    t50 = tiers[2]
    assert t50["taux_marque_pct"] == 50
    assert t50["pv"] == Decimal("20.00")
    assert t50["marge"] == Decimal("10.00")


def test_calculer_tiers_pa_negatif():
    with pytest.raises(ValueError):
        calculer_tiers(Decimal("-1"), Decimal("0"))


def test_calculer_tiers_frais_negatifs():
    with pytest.raises(ValueError):
        calculer_tiers(Decimal("10"), Decimal("-1"))


def test_taux_marge_sur_cout():
    tiers = calculer_tiers(Decimal("10"), Decimal("0"))
    # C = 10 ; PV 30% = 10/0.7 ≈ 14.29 ; M ≈ 4.29 ; taux_marge_cout = 4.29/10 * 100 ≈ 42.86
    t30 = tiers[0]
    # PV arrondi à 14.29 → M = 4.29 → 4.29/10*100 = 42.90
    assert t30["taux_marge_cout_pct"] == Decimal("42.90")
