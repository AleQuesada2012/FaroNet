//! Public, read-only replica of the signed mesh directory (RFC FN-1 5.2, 7.6).
//!
//! The Gateway publishes entries through POST /gateway/directory (HMAC as in
//! `gateway.rs`); anyone reads them from GET /directory. The Edge verifies
//! every entry itself (format, Node ID, lifetime, Ed25519 signature), so a
//! compromised Gateway can withhold entries but never forge one. Readers
//! should still verify, since they need not trust the Edge either.

use ed25519_dalek::{Signature, VerifyingKey};
use sha2::{Digest, Sha256};

pub const PREFIX: &[u8] = b"FARONET-DIRECTORY-V1";
pub const MAX_LIFETIME: u64 = 30 * 24 * 3600;
pub const CLOCK_SKEW: u64 = 60;
pub const MAX_ENTRIES: usize = 256;
const FIXED: usize = 20 + 16 + 32 + 32 + 8 + 8 + 1;
const SIGNATURE: usize = 64;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EntryError {
    Malformed,
    NodeId,
    Lifetime,
    Signature,
    NotValidNow,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub node_id: [u8; 16],
    pub issued_at: u64,
    pub expires_at: u64,
    pub bytes: Vec<u8>,
}

fn u64_at(raw: &[u8], offset: usize) -> u64 {
    let mut bytes = [0_u8; 8];
    bytes.copy_from_slice(&raw[offset..offset + 8]);
    u64::from_be_bytes(bytes)
}

/// Verify one canonical entry exactly as the Python Directory does, and that it is usable now.
pub fn verify_entry(raw: &[u8], now: u64) -> Result<Entry, EntryError> {
    if raw.len() < FIXED + SIGNATURE || !raw.starts_with(PREFIX) {
        return Err(EntryError::Malformed);
    }
    let alias_len = usize::from(raw[FIXED - 1]);
    if alias_len > 16 || raw.len() != FIXED + alias_len + SIGNATURE {
        return Err(EntryError::Malformed);
    }
    let alias = &raw[FIXED..FIXED + alias_len];
    if !alias
        .iter()
        .all(|b| b.is_ascii_alphanumeric() || *b == b'-' || *b == b'_')
    {
        return Err(EntryError::Malformed);
    }
    let mut node_id = [0_u8; 16];
    node_id.copy_from_slice(&raw[20..36]);
    let mut verify_key = [0_u8; 32];
    verify_key.copy_from_slice(&raw[36..68]);
    if Sha256::digest(verify_key)[..16] != node_id {
        return Err(EntryError::NodeId);
    }
    let issued_at = u64_at(raw, 100);
    let expires_at = u64_at(raw, 108);
    if !(issued_at < expires_at && expires_at <= issued_at.saturating_add(MAX_LIFETIME)) {
        return Err(EntryError::Lifetime);
    }
    let signed = &raw[..raw.len() - SIGNATURE];
    let mut signature = [0_u8; SIGNATURE];
    signature.copy_from_slice(&raw[raw.len() - SIGNATURE..]);
    let key = VerifyingKey::from_bytes(&verify_key).map_err(|_| EntryError::Signature)?;
    key.verify_strict(signed, &Signature::from_bytes(&signature))
        .map_err(|_| EntryError::Signature)?;
    if now.saturating_add(CLOCK_SKEW) < issued_at || now > expires_at {
        return Err(EntryError::NotValidNow);
    }
    Ok(Entry {
        node_id,
        issued_at,
        expires_at,
        bytes: raw.to_vec(),
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    Store,
    Unchanged,
    Older,
    Full,
}

/// A newer entry for a Node ID replaces the stored one, never the reverse (5.2).
pub fn decide(current_issued: Option<u64>, issued: u64, stored: usize) -> Decision {
    match current_issued {
        None if stored >= MAX_ENTRIES => Decision::Full,
        None => Decision::Store,
        Some(current) if issued > current => Decision::Store,
        Some(current) if issued == current => Decision::Unchanged,
        Some(_) => Decision::Older,
    }
}

pub fn to_hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// GET /directory body: hex entries only, so readers verify the same bytes.
pub fn directory_json(entries: &[Vec<u8>]) -> String {
    let items: Vec<String> = entries
        .iter()
        .map(|e| format!("\"{}\"", to_hex(e)))
        .collect();
    format!("{{\"version\":1,\"entries\":[{}]}}", items.join(","))
}

#[cfg(target_arch = "wasm32")]
pub mod runtime {
    use super::*;
    use worker::*;

    fn now_seconds() -> u64 {
        Date::now().as_millis() / 1000
    }

    /// The single replica. Rows: Node ID, entry bytes, issued and expiry times.
    #[durable_object]
    pub struct DirectoryReplica {
        state: State,
    }

    impl DirectoryReplica {
        fn table(&self) -> Result<worker::SqlStorage> {
            let sql = self.state.storage().sql();
            sql.exec(
                "CREATE TABLE IF NOT EXISTS entries (node_id TEXT PRIMARY KEY, entry BLOB NOT NULL, issued INTEGER NOT NULL, expires INTEGER NOT NULL)",
                None,
            )?;
            sql.exec(
                "DELETE FROM entries WHERE expires < ?",
                vec![(now_seconds() as i64).into()],
            )?;
            Ok(sql)
        }

        fn blobs(rows: Vec<Result<Vec<worker::SqlStorageValue>>>) -> Vec<Vec<u8>> {
            rows.into_iter()
                .filter_map(|row| row.ok())
                .flat_map(|values| values.into_iter())
                .filter_map(|value| match value {
                    worker::SqlStorageValue::Blob(bytes) => Some(bytes),
                    _ => None,
                })
                .collect()
        }
    }

    impl DurableObject for DirectoryReplica {
        fn new(state: State, _env: Env) -> Self {
            Self { state }
        }

        async fn fetch(&self, mut req: Request) -> Result<Response> {
            let sql = self.table()?;
            if req.method() == Method::Get {
                let rows = sql
                    .exec("SELECT entry FROM entries ORDER BY node_id", None)?
                    .raw()
                    .collect();
                let mut response = Response::ok(directory_json(&Self::blobs(rows)))?;
                let headers = response.headers_mut();
                headers.set("Content-Type", "application/json; charset=utf-8")?;
                headers.set("Cache-Control", "public, max-age=30")?;
                headers.set("X-Content-Type-Options", "nosniff")?;
                return Ok(response);
            }
            let raw = req.bytes().await?;
            let Ok(entry) = verify_entry(&raw, now_seconds()) else {
                return Response::error("Entrada de directorio inválida", 400);
            };
            let id = to_hex(&entry.node_id);
            let current = sql
                .exec(
                    "SELECT issued FROM entries WHERE node_id = ?",
                    vec![id.clone().into()],
                )?
                .raw()
                .filter_map(|row| row.ok())
                .flat_map(|values| values.into_iter())
                .find_map(|value| match value {
                    worker::SqlStorageValue::Integer(issued) => u64::try_from(issued).ok(),
                    _ => None,
                });
            let stored = sql.exec("SELECT node_id FROM entries", None)?.raw().count();
            match decide(current, entry.issued_at, stored) {
                Decision::Store => {
                    sql.exec(
                        "INSERT INTO entries (node_id, entry, issued, expires) VALUES (?, ?, ?, ?) ON CONFLICT(node_id) DO UPDATE SET entry = excluded.entry, issued = excluded.issued, expires = excluded.expires",
                        vec![
                            id.into(),
                            entry.bytes.into(),
                            (entry.issued_at as i64).into(),
                            (entry.expires_at as i64).into(),
                        ],
                    )?;
                    // Erase expired entries even when nobody publishes or reads.
                    self.state
                        .storage()
                        .set_alarm(std::time::Duration::from_secs(3600))
                        .await?;
                    Ok(Response::empty()?.with_status(201))
                }
                Decision::Unchanged => Ok(Response::empty()?.with_status(200)),
                Decision::Older => Response::error("Ya hay una entrada más reciente", 409),
                Decision::Full => Response::error("El directorio está lleno", 507),
            }
        }

        async fn alarm(&self) -> Result<Response> {
            let sql = self.table()?;
            let left = sql.exec("SELECT node_id FROM entries", None)?.raw().count();
            if left > 0 {
                self.state
                    .storage()
                    .set_alarm(std::time::Duration::from_secs(3600))
                    .await?;
            }
            Response::empty()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn vector() -> (Vec<u8>, u64) {
        let text = std::fs::read_to_string(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../fixtures/directory-v1.json"
        ))
        .unwrap();
        let data: serde_json::Value = serde_json::from_str(&text).unwrap();
        let v = &data["vectors"][0];
        let hex = v["entry_hex"].as_str().unwrap();
        let bytes = (0..hex.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
            .collect();
        (bytes, v["issued_at"].as_u64().unwrap())
    }

    #[test]
    fn python_signed_vector_verifies() {
        let (raw, issued) = vector();
        let entry = verify_entry(&raw, issued).unwrap();
        assert_eq!(to_hex(&entry.node_id), "56475aa75463474c0285df5dbf2bcab7");
        assert_eq!(entry.issued_at, issued);
        assert!(verify_entry(&raw, issued - CLOCK_SKEW).is_ok());
        assert_eq!(
            verify_entry(&raw, issued - CLOCK_SKEW - 1),
            Err(EntryError::NotValidNow)
        );
        assert_eq!(
            verify_entry(&raw, entry.expires_at + 1),
            Err(EntryError::NotValidNow)
        );
    }

    #[test]
    fn tampering_is_rejected() {
        let (raw, issued) = vector();
        let mut alias = raw.clone();
        alias[FIXED] ^= 1; // alias byte: still ASCII, but no longer signed
        assert_eq!(verify_entry(&alias, issued), Err(EntryError::Signature));
        let mut id = raw.clone();
        id[20] ^= 1;
        assert_eq!(verify_entry(&id, issued), Err(EntryError::NodeId));
        let mut expiry = raw.clone();
        expiry[108] = 0xff; // expiry far beyond 30 days
        assert_eq!(verify_entry(&expiry, issued), Err(EntryError::Lifetime));
        let mut bad_alias = raw.clone();
        bad_alias[FIXED] = b'!';
        assert_eq!(verify_entry(&bad_alias, issued), Err(EntryError::Malformed));
        assert_eq!(
            verify_entry(&raw[..raw.len() - 1], issued),
            Err(EntryError::Malformed)
        );
        let mut prefix = raw.clone();
        prefix[0] = b'X';
        assert_eq!(verify_entry(&prefix, issued), Err(EntryError::Malformed));
    }

    #[test]
    fn newer_replaces_older_never_and_size_is_capped() {
        assert_eq!(decide(None, 5, 0), Decision::Store);
        assert_eq!(decide(Some(5), 6, 1), Decision::Store);
        assert_eq!(decide(Some(5), 5, 1), Decision::Unchanged);
        assert_eq!(decide(Some(5), 4, 1), Decision::Older);
        assert_eq!(decide(None, 5, MAX_ENTRIES), Decision::Full);
        assert_eq!(decide(Some(5), 6, MAX_ENTRIES), Decision::Store);
    }

    #[test]
    fn json_lists_hex_entries() {
        assert_eq!(directory_json(&[]), "{\"version\":1,\"entries\":[]}");
        assert_eq!(
            directory_json(&[vec![0xab, 0x01], vec![0x00]]),
            "{\"version\":1,\"entries\":[\"ab01\",\"00\"]}"
        );
    }
}
