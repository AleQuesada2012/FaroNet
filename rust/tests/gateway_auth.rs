//! Contract fixtures are public synthetic data, shared with the Python tests.

use faronet_edge::gateway_auth::{
    sign_request, testing::FakeNonceStore, AuthError, GatewayRequest, Verifier, MAX_BODY_BYTES,
};
use serde_json::Value;
use sha2::{Digest, Sha256};

struct Fixture {
    data: Value,
    secret: Vec<u8>,
    body: Vec<u8>,
}

fn field<'a>(value: &'a Value, name: &str) -> &'a str {
    value[name].as_str().unwrap()
}

fn from_hex(value: &str) -> Vec<u8> {
    (0..value.len())
        .step_by(2)
        .map(|index| u8::from_str_radix(&value[index..index + 2], 16).unwrap())
        .collect()
}

fn fixtures() -> Vec<Fixture> {
    let data: Value =
        serde_json::from_str(include_str!("../../fixtures/gateway-auth-v1.json")).unwrap();
    data["vectors"]
        .as_array()
        .unwrap()
        .iter()
        .map(|data| Fixture {
            secret: from_hex(field(data, "secret_hex")),
            body: from_hex(field(data, "body_hex")),
            data: data.clone(),
        })
        .collect()
}

impl Fixture {
    fn request(&self) -> GatewayRequest<'_> {
        GatewayRequest {
            audience: field(&self.data, "audience"),
            key_id: field(&self.data, "key_id"),
            method: field(&self.data, "method"),
            path: field(&self.data, "path"),
            timestamp: field(&self.data, "timestamp"),
            nonce: field(&self.data, "nonce"),
            body: &self.body,
        }
    }

    fn signature(&self) -> &str {
        field(&self.data, "signature_hex")
    }

    fn now(&self) -> u64 {
        self.request().timestamp.parse().unwrap()
    }

    fn verifier(&self) -> Verifier<'_> {
        Verifier::new("faronet-test", "gateway-test", &self.secret).unwrap()
    }

    fn admit(
        &self,
        request: &GatewayRequest<'_>,
        signature: &str,
        now: u64,
        store: &mut FakeNonceStore,
    ) -> Result<(), AuthError> {
        self.verifier()
            .verify_and_admit(request, signature, &mut || now, store)
    }
}

#[test]
fn shared_vectors_match_canonical_bytes_hash_mac_and_admission() {
    for fixture in fixtures() {
        let request = fixture.request();
        assert_eq!(
            request.canonical_bytes().unwrap(),
            field(&fixture.data, "canonical").as_bytes()
        );
        let digest: String = Sha256::digest(request.body)
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect();
        assert_eq!(digest, field(&fixture.data, "body_sha256"));
        assert_eq!(
            sign_request(&request, &fixture.secret).unwrap(),
            fixture.signature()
        );
        assert_eq!(
            fixture.admit(
                &request,
                fixture.signature(),
                fixture.now(),
                &mut FakeNonceStore::default()
            ),
            Ok(())
        );
    }
}

#[test]
fn every_bound_field_and_wrong_key_fail_without_admission() {
    let fixture = fixtures().remove(0);
    let timestamp = (fixture.now() + 1).to_string();
    let altered = [
        GatewayRequest {
            audience: "another-environment",
            ..fixture.request()
        },
        GatewayRequest {
            key_id: "another-gateway",
            ..fixture.request()
        },
        GatewayRequest {
            method: "GET",
            ..fixture.request()
        },
        GatewayRequest {
            path: "/v1/other",
            ..fixture.request()
        },
        GatewayRequest {
            timestamp: &timestamp,
            ..fixture.request()
        },
        GatewayRequest {
            nonce: "ffffffffffffffffffffffffffffffff",
            ..fixture.request()
        },
        GatewayRequest {
            body: b"changed",
            ..fixture.request()
        },
    ];
    let mut store = FakeNonceStore::default();
    for request in altered {
        assert!(fixture
            .admit(&request, fixture.signature(), fixture.now(), &mut store)
            .is_err());
        assert_eq!(store.count(), 0);
    }
    let wrong_key = [b'X'; 32];
    let verifier = Verifier::new("faronet-test", "gateway-test", &wrong_key).unwrap();
    assert_eq!(
        verifier.verify_and_admit(
            &fixture.request(),
            fixture.signature(),
            &mut || fixture.now(),
            &mut store
        ),
        Err(AuthError::Authentication)
    );
    assert_eq!(store.count(), 0);
}

#[test]
fn method_is_bound_when_both_requests_are_valid() {
    let fixture = fixtures().remove(1);
    let request = GatewayRequest {
        method: "POST",
        ..fixture.request()
    };
    assert_eq!(
        fixture.admit(
            &request,
            fixture.signature(),
            fixture.now(),
            &mut FakeNonceStore::default()
        ),
        Err(AuthError::Authentication)
    );
}

#[test]
fn noncanonical_request_fields_are_rejected() {
    let fixture = fixtures().remove(0);
    let altered = [
        GatewayRequest {
            audience: "",
            ..fixture.request()
        },
        GatewayRequest {
            audience: "tést",
            ..fixture.request()
        },
        GatewayRequest {
            key_id: "gateway\n",
            ..fixture.request()
        },
        GatewayRequest {
            method: "post",
            ..fixture.request()
        },
        GatewayRequest {
            path: "/v1/test?x=1",
            ..fixture.request()
        },
        GatewayRequest {
            path: "/v1/test#part",
            ..fixture.request()
        },
        GatewayRequest {
            path: "/v1/%74est",
            ..fixture.request()
        },
        GatewayRequest {
            path: "/v1//test",
            ..fixture.request()
        },
        GatewayRequest {
            path: "/v1/../test",
            ..fixture.request()
        },
        GatewayRequest {
            path: "/v1/test/",
            ..fixture.request()
        },
        GatewayRequest {
            path: "/v1/a.b",
            ..fixture.request()
        },
        GatewayRequest {
            path: "relative",
            ..fixture.request()
        },
        GatewayRequest {
            timestamp: "01",
            ..fixture.request()
        },
        GatewayRequest {
            timestamp: "+1",
            ..fixture.request()
        },
        GatewayRequest {
            timestamp: "-1",
            ..fixture.request()
        },
        GatewayRequest {
            timestamp: "1.5",
            ..fixture.request()
        },
        GatewayRequest {
            timestamp: " 1",
            ..fixture.request()
        },
        GatewayRequest {
            timestamp: "١",
            ..fixture.request()
        },
        GatewayRequest {
            timestamp: "18446744073709551616",
            ..fixture.request()
        },
        GatewayRequest {
            nonce: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            ..fixture.request()
        },
        GatewayRequest {
            nonce: "gggggggggggggggggggggggggggggggg",
            ..fixture.request()
        },
        GatewayRequest {
            nonce: "short",
            ..fixture.request()
        },
    ];
    for request in altered {
        assert_eq!(request.validate(), Err(AuthError::InvalidInput));
    }
}

#[test]
fn invalid_mac_encoding_and_value_fail() {
    let fixture = fixtures().remove(0);
    let signatures = [
        fixture.signature().to_uppercase(),
        fixture.signature()[1..].to_owned(),
        "g".repeat(64),
        "0".repeat(64),
    ];
    let mut store = FakeNonceStore::default();
    for signature in signatures {
        assert!(fixture
            .admit(&fixture.request(), &signature, fixture.now(), &mut store)
            .is_err());
    }
    assert_eq!(store.count(), 0);
}

#[test]
fn body_cap_get_constraint_and_short_keys() {
    let fixture = fixtures().remove(0);
    let body = vec![b'x'; MAX_BODY_BYTES];
    let request = GatewayRequest {
        body: &body,
        ..fixture.request()
    };
    let signature = sign_request(&request, &fixture.secret).unwrap();
    assert_eq!(
        fixture.admit(
            &request,
            &signature,
            fixture.now(),
            &mut FakeNonceStore::default()
        ),
        Ok(())
    );
    let oversized = vec![b'x'; MAX_BODY_BYTES + 1];
    assert_eq!(
        GatewayRequest {
            body: &oversized,
            ..fixture.request()
        }
        .validate(),
        Err(AuthError::InvalidInput)
    );
    assert_eq!(
        GatewayRequest {
            method: "GET",
            ..fixture.request()
        }
        .validate(),
        Err(AuthError::InvalidInput)
    );
    assert!(Verifier::new("faronet-test", "gateway-test", &[0; 31]).is_err());
    assert_eq!(
        sign_request(&fixture.request(), &[0; 31]),
        Err(AuthError::InvalidSecret)
    );
}

#[test]
fn clock_window_is_inclusive() {
    let fixture = fixtures().remove(0);
    let now = fixture.now();
    for time in [now - 60, now, now + 60] {
        assert_eq!(
            fixture.admit(
                &fixture.request(),
                fixture.signature(),
                time,
                &mut FakeNonceStore::default()
            ),
            Ok(())
        );
    }
    for time in [now - 61, now + 61] {
        assert_eq!(
            fixture.admit(
                &fixture.request(),
                fixture.signature(),
                time,
                &mut FakeNonceStore::default()
            ),
            Err(AuthError::Stale)
        );
    }
}

#[test]
fn zero_and_max_timestamp_expiry_do_not_wrap() {
    for fixture in fixtures().into_iter().skip(2) {
        let mut store = FakeNonceStore::default();
        assert_eq!(
            fixture.admit(
                &fixture.request(),
                fixture.signature(),
                fixture.now(),
                &mut store
            ),
            Ok(())
        );
        assert_eq!(
            fixture.admit(
                &fixture.request(),
                fixture.signature(),
                fixture.now(),
                &mut store
            ),
            Err(AuthError::Replay)
        );
    }
}

#[test]
fn replay_is_rejected() {
    let fixture = fixtures().remove(0);
    let mut store = FakeNonceStore::default();
    assert_eq!(
        fixture.admit(
            &fixture.request(),
            fixture.signature(),
            fixture.now(),
            &mut store
        ),
        Ok(())
    );
    assert_eq!(
        fixture.admit(
            &fixture.request(),
            fixture.signature(),
            fixture.now(),
            &mut store
        ),
        Err(AuthError::Replay)
    );
    assert_eq!(store.count(), 1);
}

#[test]
fn future_nonce_retention_covers_full_acceptance_window() {
    let fixture = fixtures().remove(0);
    let now = fixture.now();
    let timestamp = (now + 60).to_string();
    let request = GatewayRequest {
        timestamp: &timestamp,
        ..fixture.request()
    };
    let signature = sign_request(&request, &fixture.secret).unwrap();
    let mut store = FakeNonceStore::default();
    assert_eq!(fixture.admit(&request, &signature, now, &mut store), Ok(()));
    for time in [now + 61, now + 120] {
        assert_eq!(
            fixture.admit(&request, &signature, time, &mut store),
            Err(AuthError::Replay)
        );
    }
    assert_eq!(
        fixture.admit(&request, &signature, now + 121, &mut store),
        Err(AuthError::Stale)
    );
    let next_timestamp = (now + 121).to_string();
    let next_request = GatewayRequest {
        timestamp: &next_timestamp,
        nonce: "ffffffffffffffffffffffffffffffff",
        ..fixture.request()
    };
    let next_signature = sign_request(&next_request, &fixture.secret).unwrap();
    assert_eq!(
        fixture.admit(&next_request, &next_signature, now + 121, &mut store),
        Ok(())
    );
    assert_eq!(store.count(), 1);
}

#[test]
fn clock_is_rechecked_at_admission() {
    let fixture = fixtures().remove(0);
    let now = fixture.now();
    let mut readings = [now + 60, now + 61].into_iter();
    let mut store = FakeNonceStore::default();
    assert_eq!(
        fixture.verifier().verify_and_admit(
            &fixture.request(),
            fixture.signature(),
            &mut || readings.next().unwrap(),
            &mut store
        ),
        Err(AuthError::Stale)
    );
    assert_eq!(store.count(), 0);
}

#[test]
fn store_failure_rejects_valid_authentication() {
    let fixture = fixtures().remove(0);
    let mut store = FakeNonceStore::default();
    store.available = false;
    assert_eq!(
        fixture.admit(
            &fixture.request(),
            fixture.signature(),
            fixture.now(),
            &mut store
        ),
        Err(AuthError::StoreUnavailable)
    );
}

#[test]
fn bad_authentication_cannot_touch_clock_or_store() {
    let fixture = fixtures().remove(0);
    let mut store = FakeNonceStore::default();
    store.available = false;
    let signature = "0".repeat(64);
    assert_eq!(
        fixture.verifier().verify_and_admit(
            &fixture.request(),
            &signature,
            &mut || panic!("Invalid authentication reached admission"),
            &mut store
        ),
        Err(AuthError::Authentication)
    );
}

#[test]
fn errors_do_not_echo_request_data() {
    let fixture = fixtures().remove(0);
    let error = fixture
        .admit(
            &fixture.request(),
            &"0".repeat(64),
            fixture.now(),
            &mut FakeNonceStore::default(),
        )
        .unwrap_err();
    let message = error.to_string();
    assert!(!message.contains(fixture.request().nonce));
    assert!(!message.contains(fixture.request().path));
    assert!(!message.contains(field(&fixture.data, "secret_hex")));
}
