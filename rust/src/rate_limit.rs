//! Per-client request limiting. Counters live only in Durable Object memory;
//! no address, key or count is written to storage or logs.

use sha2::{Digest, Sha256};

pub const REQUEST_LIMIT: u64 = 60;
pub const REQUEST_PERIOD_MS: u64 = 60_000;

/// Fixed-window counter: `window` is [start ms, count]; None once `limit` is spent.
pub fn admit_in_window(
    window: [u64; 2],
    now_ms: u64,
    period_ms: u64,
    limit: u64,
) -> Option<[u64; 2]> {
    let mut next = if now_ms.saturating_sub(window[0]) >= period_ms {
        [now_ms, 0]
    } else {
        window
    };
    if next[1] >= limit {
        return None;
    }
    next[1] += 1;
    Some(next)
}

/// Limiter object name for a client. Hashing keeps the raw address out of the
/// name; it is not anonymization (IPv4 hashes are easy to reverse by search).
pub fn limiter_key(client: Option<&str>) -> String {
    let mut hash = Sha256::new();
    hash.update(b"faronet-edge-rate-limit-v1\0");
    hash.update(client.unwrap_or("unknown").as_bytes());
    hash.finalize()[..16]
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

#[cfg(target_arch = "wasm32")]
pub mod runtime {
    use super::*;
    use std::cell::Cell;
    use worker::*;

    #[durable_object]
    pub struct EdgeLimiter {
        window: Cell<[u64; 2]>,
    }

    impl DurableObject for EdgeLimiter {
        fn new(_state: State, _env: Env) -> Self {
            Self {
                window: Cell::new([0, 0]),
            }
        }

        async fn fetch(&self, _req: Request) -> Result<Response> {
            // Memory only: an evicted limiter simply starts a fresh window.
            let now = Date::now().as_millis();
            match admit_in_window(self.window.get(), now, REQUEST_PERIOD_MS, REQUEST_LIMIT) {
                Some(next) => {
                    self.window.set(next);
                    Response::empty()
                }
                None => Response::error("Too many requests", 429),
            }
        }
    }

    /// Count this request against its client's window; false once the limit is spent.
    pub async fn admitted(request: &Request, env: &Env) -> Result<bool> {
        let client = request.headers().get("CF-Connecting-IP")?;
        let key = limiter_key(client.as_deref());
        let response = env
            .durable_object("EDGE_LIMITER")?
            .get_by_name(&key)?
            .fetch_with_str("https://limiter.invalid/admit")
            .await?;
        Ok(response.status_code() == 200)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn window_allows_the_limit_then_resets_after_the_period() {
        let mut window = [0, 0];
        for _ in 0..REQUEST_LIMIT {
            window = admit_in_window(window, 70_000, REQUEST_PERIOD_MS, REQUEST_LIMIT).unwrap();
        }
        assert_eq!(
            admit_in_window(window, 129_999, REQUEST_PERIOD_MS, REQUEST_LIMIT),
            None
        );
        assert_eq!(
            admit_in_window(window, 130_000, REQUEST_PERIOD_MS, REQUEST_LIMIT),
            Some([130_000, 1])
        );
    }

    #[test]
    fn keys_are_stable_distinct_and_never_contain_the_address() {
        let key = limiter_key(Some("203.0.113.7"));
        assert_eq!(key, limiter_key(Some("203.0.113.7")));
        assert_eq!(key.len(), 32);
        assert!(key.bytes().all(|b| b.is_ascii_hexdigit()));
        assert!(!key.contains("203"));
        assert_ne!(key, limiter_key(Some("203.0.113.8")));
        assert_ne!(key, limiter_key(None));
    }
}
