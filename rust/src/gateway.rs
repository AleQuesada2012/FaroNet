//! Gateway routes: authenticated relay into public topics, and the dead drop.
//!
//! Every route is signed with the `gateway_auth` HMAC contract (RFC FN-1
//! Section 6). Syntax, scope, MAC, freshness and the body are checked first;
//! then the nonce is claimed in the `GatewayReplay` Durable Object, which
//! stores only nonce and expiry; only then does the route have any effect.
//! The routes answer 404 unless GATEWAY_SECRET is configured.
//!
//! Dead drop: a slot named by 64 lowercase hex digits (derived by both
//! parties from a shared secret) holds one opaque blob of exactly
//! DROP_BYTES for at most DROP_TTL_SECONDS. A slot is written once and
//! deleted when read. The Edge never sees keys or plaintext.

use crate::gateway_auth::{AuthError, CLOCK_TOLERANCE};
use crate::public_rooms::{valid_message, valid_room, MAX_MESSAGE_BYTES};

pub const DROP_BYTES: usize = 1024;
pub const DROP_TTL_SECONDS: u64 = 24 * 3600;
pub const KEY_HEADER: &str = "X-FaroNet-Key";
pub const TIMESTAMP_HEADER: &str = "X-FaroNet-Timestamp";
pub const NONCE_HEADER: &str = "X-FaroNet-Nonce";
pub const SIGNATURE_HEADER: &str = "X-FaroNet-Signature";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Route<'a> {
    Relay(&'a str),
    DropPut(&'a str),
    DropTake(&'a str),
    DirectoryPublish,
}

fn lower_hex(value: &str, length: usize) -> bool {
    value.len() == length
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

pub fn valid_drop_id(id: &str) -> bool {
    lower_hex(id, 64)
}

/// The route for a method and path, or the HTTP status to answer.
pub fn route<'a>(method: &str, path: &'a str) -> Result<Route<'a>, u16> {
    if let Some(topic) = path.strip_prefix("/gateway/rooms/") {
        if !valid_room(topic) {
            return Err(404);
        }
        return if method == "POST" {
            Ok(Route::Relay(topic))
        } else {
            Err(405)
        };
    }
    if path == "/gateway/directory" {
        return if method == "POST" {
            Ok(Route::DirectoryPublish)
        } else {
            Err(405)
        };
    }
    if let Some(id) = path.strip_prefix("/gateway/drop/") {
        if !valid_drop_id(id) {
            return Err(404);
        }
        return match method {
            "POST" => Ok(Route::DropPut(id)),
            "GET" => Ok(Route::DropTake(id)),
            _ => Err(405),
        };
    }
    Err(404)
}

/// Body rules per route, checked before the nonce is claimed.
pub fn valid_body(route: Route<'_>, body: &[u8]) -> bool {
    match route {
        Route::Relay(_) => {
            body.len() <= MAX_MESSAGE_BYTES && std::str::from_utf8(body).is_ok_and(valid_message)
        }
        Route::DropPut(_) => body.len() == DROP_BYTES,
        Route::DropTake(_) => body.is_empty(),
        // Shape only; directory.rs verifies the entry itself.
        Route::DirectoryPublish => (181..=197).contains(&body.len()),
    }
}

/// Status for a rejected request; the body is always a static message.
pub fn auth_status(error: AuthError) -> u16 {
    match error {
        AuthError::InvalidInput => 400,
        AuthError::Replay => 409,
        AuthError::StoreUnavailable | AuthError::InvalidSecret => 503,
        AuthError::WrongScope | AuthError::Authentication | AuthError::Stale => 401,
    }
}

/// The configured secret: lowercase hex of at least 32 bytes.
pub fn decode_secret(hex: &str) -> Option<Vec<u8>> {
    if hex.len() < 64 || !hex.len().is_multiple_of(2) || !lower_hex(hex, hex.len()) {
        return None;
    }
    (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).ok())
        .collect()
}

/// Internal claim request between the Worker and GatewayReplay: "<nonce> <timestamp>".
pub fn parse_claim(body: &str) -> Option<(&str, u64)> {
    let (nonce, timestamp) = body.split_once(' ')?;
    if !lower_hex(nonce, 32) {
        return None;
    }
    Some((nonce, timestamp.parse().ok()?))
}

/// A claim is kept until timestamp + 60 s, after which the request is stale anyway.
pub fn claim_expiry(timestamp: u64) -> u64 {
    timestamp.saturating_add(CLOCK_TOLERANCE)
}

#[cfg(target_arch = "wasm32")]
pub mod runtime {
    use super::*;
    use crate::gateway_auth::{check_freshness, GatewayRequest, Verifier};
    use worker::js_sys::Uint8Array;
    use worker::wasm_bindgen::JsValue;
    use worker::*;

    fn now_seconds() -> u64 {
        Date::now().as_millis() / 1000
    }

    fn reject(status: u16) -> Result<Response> {
        let message = match status {
            400 => "Solicitud del gateway inválida",
            401 => "Autenticación fallida",
            404 => "No encontrado",
            405 => "Método no permitido",
            409 => "Solicitud ya admitida",
            _ => "Gateway no disponible",
        };
        Response::error(message, status)
    }

    fn internal(path: &str, method: Method, body: Option<JsValue>) -> Result<Request> {
        let mut init = RequestInit::new();
        init.with_method(method).with_body(body);
        Request::new_with_init(&format!("https://gateway.internal{path}"), &init)
    }

    /// Entry for every /gateway/ path.
    pub async fn handle(mut req: Request, env: &Env) -> Result<Response> {
        let path = req.path();
        let method = req.method().to_string();
        let route = match route(&method, &path) {
            Ok(route) => route,
            Err(status) => return reject(status),
        };
        let config = (
            env.var("GATEWAY_AUDIENCE"),
            env.var("GATEWAY_KEY_ID"),
            env.var("GATEWAY_SECRET"),
        );
        let (Ok(audience), Ok(key_id), Ok(secret)) = config else {
            return reject(404);
        };
        let (audience, key_id) = (audience.to_string(), key_id.to_string());
        let Some(secret) = decode_secret(&secret.to_string()) else {
            return reject(503);
        };
        let Ok(verifier) = Verifier::new(&audience, &key_id, &secret) else {
            return reject(503);
        };
        if req.url()?.query().is_some() {
            return reject(400);
        }
        let header =
            |name: &str| -> Result<String> { Ok(req.headers().get(name)?.unwrap_or_default()) };
        let (key, timestamp, nonce, signature) = (
            header(KEY_HEADER)?,
            header(TIMESTAMP_HEADER)?,
            header(NONCE_HEADER)?,
            header(SIGNATURE_HEADER)?,
        );
        let body = req.bytes().await?;
        let request = GatewayRequest {
            audience: &audience,
            key_id: &key,
            method: &method,
            path: &path,
            timestamp: &timestamp,
            nonce: &nonce,
            body: &body,
        };
        let timestamp = match verifier.authenticate(&request, &signature, now_seconds()) {
            Ok(timestamp) => timestamp,
            Err(error) => return reject(auth_status(error)),
        };
        if !valid_body(route, &body) {
            return reject(400);
        }
        // Fail closed: any storage problem rejects before the route has an effect.
        let claim = internal(
            "/claim",
            Method::Post,
            Some(JsValue::from_str(&format!("{nonce} {timestamp}"))),
        )?;
        let claimed = match env.durable_object("GATEWAY_REPLAY") {
            Ok(namespace) => match namespace.get_by_name(&format!("{audience}.{key_id}")) {
                Ok(stub) => stub
                    .fetch_with_request(claim)
                    .await
                    .map(|r| r.status_code()),
                Err(error) => Err(error),
            },
            Err(error) => Err(error),
        };
        match claimed {
            Ok(200) => {}
            Ok(409) => return reject(409),
            Ok(401) => return reject(401),
            _ => return reject(503),
        }
        match route {
            Route::Relay(topic) => {
                let relay = internal(
                    "/gateway-relay",
                    Method::Post,
                    Some(JsValue::from_str(
                        std::str::from_utf8(&body).unwrap_or_default(),
                    )),
                )?;
                env.durable_object("PUBLIC_ROOMS")?
                    .get_by_name(topic)?
                    .fetch_with_request(relay)
                    .await
            }
            Route::DropPut(id) => {
                let blob = Uint8Array::from(body.as_slice());
                env.durable_object("DEAD_DROPS")?
                    .get_by_name(id)?
                    .fetch_with_request(internal("/put", Method::Post, Some(blob.into()))?)
                    .await
            }
            Route::DirectoryPublish => {
                let entry = Uint8Array::from(body.as_slice());
                env.durable_object("DIRECTORY")?
                    .get_by_name("replica")?
                    .fetch_with_request(internal("/publish", Method::Post, Some(entry.into()))?)
                    .await
            }
            Route::DropTake(id) => {
                env.durable_object("DEAD_DROPS")?
                    .get_by_name(id)?
                    .fetch_with_request(internal("/take", Method::Post, None)?)
                    .await
            }
        }
    }

    /// Nonce claims for one (audience, key ID): only nonce and expiry are stored.
    #[durable_object]
    pub struct GatewayReplay {
        state: State,
    }

    impl DurableObject for GatewayReplay {
        fn new(state: State, _env: Env) -> Self {
            Self { state }
        }

        async fn fetch(&self, mut req: Request) -> Result<Response> {
            let body = req.text().await?;
            let Some((nonce, timestamp)) = parse_claim(&body) else {
                return Response::error("Invalid claim", 400);
            };
            // Read the clock again inside the store, as the contract requires.
            let now = now_seconds();
            if check_freshness(timestamp, now).is_err() {
                return Response::error("Stale", 401);
            }
            let sql = self.state.storage().sql();
            sql.exec(
                "CREATE TABLE IF NOT EXISTS claims (nonce TEXT PRIMARY KEY, expires INTEGER NOT NULL)",
                None,
            )?;
            sql.exec(
                "DELETE FROM claims WHERE expires < ?",
                vec![(now as i64).into()],
            )?;
            let inserted = sql
                .exec(
                    "INSERT INTO claims (nonce, expires) VALUES (?, ?) ON CONFLICT(nonce) DO NOTHING RETURNING 1",
                    vec![nonce.into(), (claim_expiry(timestamp) as i64).into()],
                )?
                .raw()
                .count();
            // Erase the table when the newest claim has expired, even if idle.
            self.state
                .storage()
                .set_alarm(std::time::Duration::from_secs(2 * CLOCK_TOLERANCE + 1))
                .await?;
            if inserted == 1 {
                Response::ok("claimed")
            } else {
                Response::error("Replay", 409)
            }
        }

        async fn alarm(&self) -> Result<Response> {
            let sql = self.state.storage().sql();
            sql.exec(
                "CREATE TABLE IF NOT EXISTS claims (nonce TEXT PRIMARY KEY, expires INTEGER NOT NULL)",
                None,
            )?;
            sql.exec(
                "DELETE FROM claims WHERE expires < ?",
                vec![(now_seconds() as i64).into()],
            )?;
            Response::empty()
        }
    }

    /// One dead-drop slot: a single fixed-size blob, written once, deleted on read or at TTL.
    #[durable_object]
    pub struct DeadDrop {
        state: State,
    }

    impl DeadDrop {
        fn table(&self) -> Result<worker::SqlStorage> {
            let sql = self.state.storage().sql();
            sql.exec(
                "CREATE TABLE IF NOT EXISTS slot (id INTEGER PRIMARY KEY CHECK (id = 1), blob BLOB NOT NULL, expires INTEGER NOT NULL)",
                None,
            )?;
            sql.exec(
                "DELETE FROM slot WHERE expires < ?",
                vec![(now_seconds() as i64).into()],
            )?;
            Ok(sql)
        }
    }

    impl DurableObject for DeadDrop {
        fn new(state: State, _env: Env) -> Self {
            Self { state }
        }

        async fn fetch(&self, mut req: Request) -> Result<Response> {
            let sql = self.table()?;
            if req.path() == "/put" {
                let blob = req.bytes().await?;
                if blob.len() != DROP_BYTES {
                    return Response::error("Blob inválido", 400);
                }
                let expires = now_seconds() + DROP_TTL_SECONDS;
                let inserted = sql
                    .exec(
                        "INSERT INTO slot (id, blob, expires) VALUES (1, ?, ?) ON CONFLICT(id) DO NOTHING RETURNING 1",
                        vec![blob.into(), (expires as i64).into()],
                    )?
                    .raw()
                    .count();
                if inserted != 1 {
                    return Response::error("Casilla ocupada", 409);
                }
                self.state
                    .storage()
                    .set_alarm(std::time::Duration::from_secs(DROP_TTL_SECONDS + 1))
                    .await?;
                return Ok(Response::empty()?.with_status(201));
            }
            // Take: read and delete together, so a blob is delivered at most once.
            let rows: Vec<_> = sql
                .exec("DELETE FROM slot RETURNING blob", None)?
                .raw()
                .collect();
            let blob = rows.into_iter().find_map(|row| match row {
                Ok(values) => values.into_iter().find_map(|value| match value {
                    worker::SqlStorageValue::Blob(bytes) => Some(bytes),
                    _ => None,
                }),
                Err(_) => None,
            });
            let Some(blob) = blob else {
                return Response::error("No encontrado", 404);
            };
            self.state.storage().delete_alarm().await?;
            let mut response = Response::from_bytes(blob)?;
            let headers = response.headers_mut();
            headers.set("Content-Type", "application/octet-stream")?;
            headers.set("Cache-Control", "no-store")?;
            Ok(response)
        }

        async fn alarm(&self) -> Result<Response> {
            self.table()?;
            Response::empty()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const ID: &str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    #[test]
    fn routes_are_canonical_and_method_checked() {
        assert_eq!(
            route("POST", "/gateway/rooms/demo-1"),
            Ok(Route::Relay("demo-1"))
        );
        assert_eq!(route("GET", "/gateway/rooms/demo-1"), Err(405));
        assert_eq!(
            route("POST", &format!("/gateway/drop/{ID}")),
            Ok(Route::DropPut(ID))
        );
        assert_eq!(
            route("GET", &format!("/gateway/drop/{ID}")),
            Ok(Route::DropTake(ID))
        );
        assert_eq!(route("PUT", &format!("/gateway/drop/{ID}")), Err(405));
        assert_eq!(
            route("POST", "/gateway/directory"),
            Ok(Route::DirectoryPublish)
        );
        assert_eq!(route("GET", "/gateway/directory"), Err(405));
        for path in [
            "/gateway/rooms/Demo",
            "/gateway/rooms/",
            "/gateway/rooms/a/b",
            "/gateway/drop/ABCDEF",
            &format!("/gateway/drop/{}", &ID[..63]),
            &format!("/gateway/drop/{}", ID.to_uppercase()),
            "/gateway/directory/x",
            "/gateway",
        ] {
            assert_eq!(route("POST", path), Err(404), "{path}");
        }
    }

    #[test]
    fn bodies_follow_each_route() {
        assert!(valid_body(
            Route::Relay("t"),
            "hola desde la mesh".as_bytes()
        ));
        assert!(!valid_body(Route::Relay("t"), b"bad\x00control"));
        assert!(!valid_body(Route::Relay("t"), &[0xff, 0xfe]));
        assert!(!valid_body(
            Route::Relay("t"),
            &[b'a'; MAX_MESSAGE_BYTES + 1]
        ));
        assert!(valid_body(Route::DropPut(ID), &[7; DROP_BYTES]));
        assert!(!valid_body(Route::DropPut(ID), &[7; DROP_BYTES - 1]));
        assert!(!valid_body(Route::DropPut(ID), &[7; DROP_BYTES + 1]));
        assert!(valid_body(Route::DropTake(ID), b""));
        assert!(!valid_body(Route::DropTake(ID), b"x"));
        assert!(valid_body(Route::DirectoryPublish, &[0; 181]));
        assert!(valid_body(Route::DirectoryPublish, &[0; 197]));
        assert!(!valid_body(Route::DirectoryPublish, &[0; 180]));
        assert!(!valid_body(Route::DirectoryPublish, &[0; 198]));
    }

    #[test]
    fn secret_claim_and_status_helpers() {
        assert_eq!(decode_secret(&"ab".repeat(32)), Some(vec![0xab; 32]));
        assert_eq!(decode_secret(&"ab".repeat(31)), None);
        assert_eq!(decode_secret(&"AB".repeat(32)), None);
        assert_eq!(decode_secret(&format!("{}a", "ab".repeat(32))), None);
        let nonce = "00112233445566778899aabbccddeeff";
        assert_eq!(
            parse_claim(&format!("{nonce} 1792000000")),
            Some((nonce, 1_792_000_000))
        );
        assert_eq!(parse_claim("short 1"), None);
        assert_eq!(parse_claim(&format!("{nonce} -1")), None);
        assert_eq!(claim_expiry(u64::MAX), u64::MAX);
        assert_eq!(claim_expiry(100), 160);
        assert_eq!(auth_status(AuthError::Replay), 409);
        assert_eq!(auth_status(AuthError::Stale), 401);
        assert_eq!(auth_status(AuthError::InvalidInput), 400);
        assert_eq!(auth_status(AuthError::StoreUnavailable), 503);
    }
}
