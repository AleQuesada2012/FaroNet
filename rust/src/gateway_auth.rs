//! The accepted offline HMAC contract. No HTTP route uses it yet.
//!
//! Keep provider admission in a durable atomic coordinator, never a Worker-
//! global cache. The fake store here is solely for local contract evidence.

use hmac::{Hmac, KeyInit, Mac};
use sha2::{Digest, Sha256};
use std::fmt;

pub const PREFIX: &str = "FARONET-GATEWAY-HMAC-V1";
pub const MAX_BODY_BYTES: usize = 65_536;
pub const CLOCK_TOLERANCE: u64 = 60;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuthError {
    InvalidInput,
    InvalidSecret,
    WrongScope,
    Authentication,
    Stale,
    Replay,
    StoreUnavailable,
}

impl fmt::Display for AuthError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // Never interpolate request fields, nonces, signatures or secrets.
        let message = match self {
            Self::InvalidInput => "Invalid canonical request",
            Self::InvalidSecret => "Gateway secret requires at least 32 bytes",
            Self::WrongScope => "Unexpected audience or gateway key",
            Self::Authentication => "Authentication failed",
            Self::Stale => "Request is outside the accepted clock window",
            Self::Replay => "Nonce already admitted",
            Self::StoreUnavailable => "Replay store unavailable",
        };
        f.write_str(message)
    }
}

impl std::error::Error for AuthError {}

fn identifier(value: &str) -> bool {
    (1..=64).contains(&value.len())
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
}

fn path(value: &str) -> bool {
    value == "/"
        || (value.starts_with('/')
            && value[1..].split('/').all(|part| {
                !part.is_empty()
                    && part
                        .bytes()
                        .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
            }))
}

fn lower_hex(value: &str, length: usize) -> bool {
    value.len() == length
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

fn to_hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn mac(secret: &[u8], input: &[u8]) -> Result<Hmac<Sha256>, AuthError> {
    if secret.len() < 32 {
        return Err(AuthError::InvalidSecret);
    }
    let mut mac = Hmac::<Sha256>::new_from_slice(secret).map_err(|_| AuthError::InvalidSecret)?;
    mac.update(input);
    Ok(mac)
}

/// Body bytes are hashed as received, without JSON parsing or reserialization.
/// This type intentionally has no Debug implementation for request metadata.
pub struct GatewayRequest<'a> {
    pub audience: &'a str,
    pub key_id: &'a str,
    pub method: &'a str,
    pub path: &'a str,
    pub timestamp: &'a str,
    pub nonce: &'a str,
    pub body: &'a [u8],
}

impl GatewayRequest<'_> {
    pub fn validate(&self) -> Result<u64, AuthError> {
        let timestamp = self.timestamp;
        if !identifier(self.audience)
            || !identifier(self.key_id)
            || !matches!(self.method, "GET" | "POST")
            || !path(self.path)
            || timestamp.is_empty()
            || timestamp.len() > 20
            || !timestamp.bytes().all(|b| b.is_ascii_digit())
            || (timestamp.len() > 1 && timestamp.starts_with('0'))
            || !lower_hex(self.nonce, 32)
            || self.body.len() > MAX_BODY_BYTES
            || (self.method == "GET" && !self.body.is_empty())
        {
            return Err(AuthError::InvalidInput);
        }
        timestamp
            .parse::<u64>()
            .map_err(|_| AuthError::InvalidInput)
    }

    pub fn canonical_bytes(&self) -> Result<Vec<u8>, AuthError> {
        self.validate()?;
        let digest = to_hex(&Sha256::digest(self.body));
        Ok(format!(
            "{PREFIX}\n{}\n{}\n{}\n{}\n{}\n{}\n{digest}\n",
            self.audience, self.key_id, self.method, self.path, self.timestamp, self.nonce,
        )
        .into_bytes())
    }
}

pub fn sign_request(request: &GatewayRequest<'_>, secret: &[u8]) -> Result<String, AuthError> {
    Ok(to_hex(
        &mac(secret, &request.canonical_bytes()?)?
            .finalize()
            .into_bytes(),
    ))
}

pub fn check_freshness(timestamp: u64, now: u64) -> Result<(), AuthError> {
    if now.abs_diff(timestamp) > CLOCK_TOLERANCE {
        Err(AuthError::Stale)
    } else {
        Ok(())
    }
}

/// Synchronous offline seam. A durable HTTP adapter must preserve these
/// semantics inside its transaction, including reading the clock again.
pub trait NonceStore {
    fn claim(
        &mut self,
        scope: (&str, &str, &str),
        timestamp: u64,
        clock: &mut dyn FnMut() -> u64,
    ) -> Result<bool, AuthError>;
}

/// Configured scope and key. Do not derive Debug for secret-bearing objects.
pub struct Verifier<'a> {
    audience: &'a str,
    key_id: &'a str,
    secret: &'a [u8],
}

impl<'a> Verifier<'a> {
    pub fn new(audience: &'a str, key_id: &'a str, secret: &'a [u8]) -> Result<Self, AuthError> {
        if !identifier(audience) || !identifier(key_id) {
            return Err(AuthError::InvalidInput);
        }
        if secret.len() < 32 {
            return Err(AuthError::InvalidSecret);
        }
        Ok(Self {
            audience,
            key_id,
            secret,
        })
    }

    /// Authenticate, check freshness, then claim a nonce before any side effect.
    pub fn verify_and_admit(
        &self,
        request: &GatewayRequest<'_>,
        signature: &str,
        clock: &mut dyn FnMut() -> u64,
        store: &mut impl NonceStore,
    ) -> Result<(), AuthError> {
        let timestamp = request.validate()?;
        if (request.audience, request.key_id) != (self.audience, self.key_id) {
            return Err(AuthError::WrongScope);
        }
        if !lower_hex(signature, 64) {
            return Err(AuthError::InvalidInput);
        }
        let mut tag = [0_u8; 32];
        for (index, pair) in signature.as_bytes().as_chunks::<2>().0.iter().enumerate() {
            // Encoding was already validated as canonical lowercase hex.
            let nibble = |b: u8| if b <= b'9' { b - b'0' } else { b - b'a' + 10 };
            tag[index] = (nibble(pair[0]) << 4) | nibble(pair[1]);
        }
        mac(self.secret, &request.canonical_bytes()?)?
            .verify_slice(&tag)
            .map_err(|_| AuthError::Authentication)?;
        check_freshness(timestamp, clock())?;
        if !store.claim(
            (request.audience, request.key_id, request.nonce),
            timestamp,
            clock,
        )? {
            return Err(AuthError::Replay);
        }
        Ok(())
    }
}

pub mod testing {
    //! One-process fake; never use it as deployed Worker replay protection.

    use super::{check_freshness, AuthError, NonceStore, CLOCK_TOLERANCE};
    use std::collections::HashMap;

    pub struct FakeNonceStore {
        pub available: bool,
        entries: HashMap<(String, String, String), u128>,
    }

    impl Default for FakeNonceStore {
        fn default() -> Self {
            Self {
                available: true,
                entries: HashMap::new(),
            }
        }
    }

    impl FakeNonceStore {
        pub fn count(&self) -> usize {
            self.entries.len()
        }
    }

    impl NonceStore for FakeNonceStore {
        fn claim(
            &mut self,
            scope: (&str, &str, &str),
            timestamp: u64,
            clock: &mut dyn FnMut() -> u64,
        ) -> Result<bool, AuthError> {
            if !self.available {
                return Err(AuthError::StoreUnavailable);
            }
            let now = clock();
            check_freshness(timestamp, now)?;
            self.entries.retain(|_, expiry| u128::from(now) <= *expiry);
            let key = (scope.0.to_owned(), scope.1.to_owned(), scope.2.to_owned());
            if self.entries.contains_key(&key) {
                return Ok(false);
            }
            // Widen BEFORE adding; a valid u64 timestamp must not wrap.
            self.entries
                .insert(key, u128::from(timestamp) + u128::from(CLOCK_TOLERANCE));
            Ok(true)
        }
    }
}
