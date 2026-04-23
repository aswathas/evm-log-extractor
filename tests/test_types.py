import pytest

from evm_log_extractor.types import (
    checksum_address,
    hex_lower,
    wei_str,
    hex_to_int,
    signed_wei_delta,
)


class TestChecksumAddress:
    def test_lowercase_input_returns_eip55(self):
        assert checksum_address("0xc0ffee254729296a45a3885639ac7e10f9d54979") == "0xc0ffee254729296a45a3885639AC7E10F9d54979"

    def test_uppercase_input_returns_eip55(self):
        assert checksum_address("0XC0FFEE254729296A45A3885639AC7E10F9D54979") == "0xc0ffee254729296a45a3885639AC7E10F9d54979"

    def test_none_returns_none(self):
        assert checksum_address(None) is None

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            checksum_address("0xnothex")


class TestHexLower:
    def test_uppercase_returns_lowercase(self):
        assert hex_lower("0xABCDEF") == "0xabcdef"

    def test_already_lower_unchanged(self):
        assert hex_lower("0xabcdef") == "0xabcdef"

    def test_none_returns_none(self):
        assert hex_lower(None) is None

    def test_missing_prefix_raises(self):
        with pytest.raises(ValueError):
            hex_lower("abcdef")


class TestWeiStr:
    def test_int_returns_decimal_string(self):
        assert wei_str(1_000_000_000_000_000_000) == "1000000000000000000"

    def test_hex_string_returns_decimal_string(self):
        assert wei_str("0xde0b6b3a7640000") == "1000000000000000000"

    def test_decimal_string_unchanged(self):
        assert wei_str("42") == "42"

    def test_none_returns_none(self):
        assert wei_str(None) is None

    def test_negative_int_returns_negative_decimal(self):
        assert wei_str(-1) == "-1"


class TestHexToInt:
    def test_hex_prefix(self):
        assert hex_to_int("0x10") == 16

    def test_already_int(self):
        assert hex_to_int(42) == 42

    def test_none_returns_none(self):
        assert hex_to_int(None) is None


class TestSignedWeiDelta:
    def test_positive_delta(self):
        assert signed_wei_delta("1000", "500") == "500"

    def test_negative_delta(self):
        assert signed_wei_delta("500", "1000") == "-500"

    def test_zero_delta(self):
        assert signed_wei_delta("100", "100") == "0"
