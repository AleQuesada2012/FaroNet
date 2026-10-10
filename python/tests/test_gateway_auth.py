"""Python side of the shared canonical request and offline replay contract."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest

from faronet.gateway.auth import (
    MAX_BODY_BYTES, AuthError, GatewayRequest, ReplayError, ReplayStoreUnavailable,
    new_nonce, sign_request, verify_and_admit,
)
from faronet.gateway.testing import FakeNonceStore

VECTORS = json.loads((Path(__file__).parents[2] / 'fixtures/gateway-auth-v1.json').read_text())['vectors']


def request_from(vector):
    return GatewayRequest(
        vector['audience'], vector['key_id'], vector['method'], vector['path'],
        vector['timestamp'], vector['nonce'], bytes.fromhex(vector['body_hex']),
    )


class GatewayAuthTests(unittest.TestCase):
    def setUp(self):
        self.vector = VECTORS[0]
        self.request = request_from(self.vector)
        self.secret = bytes.fromhex(self.vector['secret_hex'])
        self.signature = self.vector['signature_hex']
        self.now = int(self.request.timestamp)
        self.store = FakeNonceStore()

    def admit(self, request=None, signature=None, *, now=None, clock=None, store=None, secret=None):
        verify_and_admit(
            self.request if request is None else request,
            self.signature if signature is None else signature,
            self.secret if secret is None else secret,
            expected_audience='faronet-test', expected_key_id='gateway-test',
            clock=clock or (lambda: self.now if now is None else now),
            store=self.store if store is None else store,
        )

    def test_shared_vectors_sign_and_admit(self):
        for vector in VECTORS:
            with self.subTest(vector=vector['name']):
                request = request_from(vector)
                secret = bytes.fromhex(vector['secret_hex'])
                self.assertEqual(request.canonical_bytes(), vector['canonical'].encode('ascii'))
                self.assertEqual(hashlib.sha256(request.body).hexdigest(), vector['body_sha256'])
                self.assertEqual(sign_request(request, secret), vector['signature_hex'])
                self.admit(request, vector['signature_hex'], now=int(request.timestamp), store=FakeNonceStore(), secret=secret)

    def test_all_bound_fields_and_key_tampering_fail_without_admission(self):
        changes = [
            dict(audience='another-environment'), dict(key_id='another-gateway'),
            dict(method='GET'), dict(path='/v1/other'),
            dict(timestamp=str(self.now + 1)), dict(nonce='ff' * 16), dict(body=b'changed'),
        ]
        for change in changes:
            with self.subTest(field=tuple(change)):
                with self.assertRaises(AuthError):
                    self.admit(replace(self.request, **change))
                self.assertEqual(self.store.count, 0)
        with self.assertRaises(AuthError):
            self.admit(secret=b'X' * 32)
        self.assertEqual(self.store.count, 0)

    def test_method_is_bound_even_when_both_requests_are_valid(self):
        vector = VECTORS[1]
        with self.assertRaises(AuthError):
            self.admit(replace(request_from(vector), method='POST'), vector['signature_hex'])

    def test_noncanonical_fields_are_rejected(self):
        changes = [
            dict(audience=''), dict(audience='tést'), dict(key_id='gateway\n'),
            dict(method='post'), dict(path='/v1/test?x=1'), dict(path='/v1/test#part'),
            dict(path='/v1/%74est'), dict(path='/v1//test'), dict(path='/v1/../test'),
            dict(path='/v1/test/'), dict(path='/v1/a.b'), dict(path='relative'),
            dict(timestamp='01'), dict(timestamp='+1'), dict(timestamp='-1'),
            dict(timestamp='1.5'), dict(timestamp=' 1'), dict(timestamp='١'),
            dict(timestamp=str(1 << 64)), dict(timestamp='9' * 100),
            dict(nonce='AA' * 16), dict(nonce='g' * 32), dict(nonce='0' * 31),
        ]
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(AuthError):
                    sign_request(replace(self.request, **change), self.secret)

    def test_invalid_mac_encoding_and_mac_value_fail(self):
        for signature in (self.signature.upper(), self.signature[:-1], 'g' * 64, '0' * 64):
            with self.assertRaises(AuthError):
                self.admit(signature=signature)
        self.assertEqual(self.store.count, 0)

    def test_body_cap_get_rule_and_short_secret(self):
        request = replace(self.request, body=b'x' * MAX_BODY_BYTES)
        self.admit(request, sign_request(request, self.secret))
        for request in (
            replace(self.request, body=b'x' * (MAX_BODY_BYTES + 1)),
            replace(self.request, body='text'), replace(self.request, method='GET'),
        ):
            with self.assertRaises(AuthError):
                sign_request(request, self.secret)
        with self.assertRaises(AuthError):
            sign_request(self.request, b'x' * 31)

    def test_inclusive_clock_window(self):
        for offset in (-60, 0, 60):
            self.admit(now=self.now + offset, store=FakeNonceStore())
        for offset in (-61, 61):
            with self.assertRaises(AuthError):
                self.admit(now=self.now + offset, store=FakeNonceStore())

    def test_zero_and_max_timestamp_arithmetic_never_wraps(self):
        for vector in VECTORS[2:]:
            request = request_from(vector)
            now = int(request.timestamp)
            store = FakeNonceStore()
            self.admit(request, vector['signature_hex'], now=now, store=store)
            with self.assertRaises(ReplayError):
                self.admit(request, vector['signature_hex'], now=now, store=store)

    def test_replay_is_rejected(self):
        self.admit()
        with self.assertRaises(ReplayError):
            self.admit()
        self.assertEqual(self.store.count, 1)

    def test_future_nonce_retained_for_entire_acceptance_window(self):
        request = replace(self.request, timestamp=str(self.now + 60))
        signature = sign_request(request, self.secret)
        self.admit(request, signature, now=self.now)
        for offset in (61, 120):
            with self.assertRaises(ReplayError):
                self.admit(request, signature, now=self.now + offset)
        with self.assertRaises(AuthError):
            self.admit(request, signature, now=self.now + 121)
        next_request = replace(self.request, timestamp=str(self.now + 121), nonce='ff' * 16)
        self.admit(next_request, sign_request(next_request, self.secret), now=self.now + 121)
        self.assertEqual(self.store.count, 1)

    def test_clock_is_rechecked_inside_admission(self):
        readings = iter((self.now + 60, self.now + 61))
        with self.assertRaises(AuthError):
            self.admit(clock=lambda: next(readings))
        self.assertEqual(self.store.count, 0)

    def test_store_failure_rejects_valid_authentication(self):
        with self.assertRaises(ReplayStoreUnavailable):
            self.admit(store=FakeNonceStore(available=False))

        class BrokenStore:
            def claim(self, *args):
                raise RuntimeError('internal storage detail')

        with self.assertRaises(ReplayStoreUnavailable) as error:
            self.admit(store=BrokenStore())
        self.assertNotIn('internal storage detail', str(error.exception))

    def test_bad_authentication_does_not_touch_clock_or_store(self):
        def unavailable_clock():
            self.fail('Invalid authentication reached freshness/admission')

        with self.assertRaises(AuthError):
            self.admit(signature='0' * 64, clock=unavailable_clock, store=FakeNonceStore(available=False))

    def test_invalid_store_result_cannot_admit(self):
        class InvalidStore:
            def claim(self, *args):
                return 'accepted'

        with self.assertRaises(ReplayStoreUnavailable):
            self.admit(store=InvalidStore())

    def test_nonce_and_error_output_contain_no_request_data(self):
        nonce = new_nonce()
        self.assertEqual(len(nonce), 32)
        self.assertEqual(nonce, bytes.fromhex(nonce).hex())
        with self.assertRaises(AuthError) as error:
            self.admit(signature='0' * 64)
        self.assertNotIn(self.request.nonce, str(error.exception))
        self.assertNotIn(self.request.path, str(error.exception))
        self.assertNotIn(self.secret.hex(), str(error.exception))


if __name__ == '__main__':
    unittest.main()
