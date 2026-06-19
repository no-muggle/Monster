"""Tests for message_handler.py — JSON message parsing and validation."""

import json

import pytest

from src.server.message_handler import build_message, parse_message


class TestParseMessage:
    """Tests for parse_message()."""

    def test_valid_pair_message(self):
        msg = parse_message('{"type":"pair","token":"abc123"}')
        assert msg is not None
        assert msg.type == "pair"
        assert msg.token == "abc123"

    def test_valid_sms_code_message(self):
        raw = (
            '{"type":"sms_code","code":"123456","sender":"10690",'
            '"body":"您的验证码是123456","timestamp":1718364800}'
        )
        msg = parse_message(raw)
        assert msg is not None
        assert msg.type == "sms_code"
        assert msg.code == "123456"
        assert msg.sender == "10690"
        assert msg.body == "您的验证码是123456"

    def test_pong_message(self):
        msg = parse_message('{"type":"pong"}')
        assert msg is not None
        assert msg.type == "pong"

    def test_disconnect_message(self):
        msg = parse_message('{"type":"disconnect"}')
        assert msg is not None
        assert msg.type == "disconnect"

    def test_unknown_type_returns_none(self):
        msg = parse_message('{"type":"unknown_type_xyz"}')
        assert msg is None

    def test_invalid_json_returns_none(self):
        msg = parse_message("not valid json {{{")
        assert msg is None

    def test_missing_type_field_returns_none(self):
        msg = parse_message('{"data":"something"}')
        assert msg is None

    def test_missing_required_token_in_pair(self):
        msg = parse_message('{"type":"pair"}')
        assert msg is None

    def test_missing_required_code_in_sms(self):
        msg = parse_message(
            '{"type":"sms_code","sender":"10690","body":"test","timestamp":1}'
        )
        assert msg is None


class TestBuildMessage:
    """Tests for build_message()."""

    def test_paired_ok(self):
        result = build_message("paired", status="ok", pc_name="TEST-PC")
        obj = json.loads(result)
        assert obj["type"] == "paired"
        assert obj["status"] == "ok"
        assert obj["pc_name"] == "TEST-PC"

    def test_paired_error(self):
        result = build_message("paired", status="error", reason="invalid_token")
        obj = json.loads(result)
        assert obj["type"] == "paired"
        assert obj["status"] == "error"

    def test_ack(self):
        result = build_message("ack", code="123456", status="ok")
        obj = json.loads(result)
        assert obj["type"] == "ack"
        assert obj["code"] == "123456"

    def test_ping(self):
        result = build_message("ping")
        obj = json.loads(result)
        assert obj["type"] == "ping"
