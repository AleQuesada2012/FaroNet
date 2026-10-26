//! Local opt-in public-room prototype. Never a private mesh endpoint.

pub const MAX_MESSAGE_BYTES: usize = 1024;
pub const MAX_CONNECTIONS: usize = 16;

pub fn room_from_path(path: &str) -> Option<&str> {
    let room = path.strip_prefix("/rooms/")?.strip_suffix("/ws")?;
    (!room.is_empty()
        && room.len() <= 32
        && room
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-'))
    .then_some(room)
}

pub fn valid_message(text: &str) -> bool {
    !text.trim().is_empty()
        && text.len() <= MAX_MESSAGE_BYTES
        && !text
            .chars()
            .any(|c| c.is_control() && c != '\n' && c != '\t')
}

/// Attachment state survives hibernation; contains only a window and count.
pub fn admit_message(window: [u64; 2], now_ms: u64) -> Option<[u64; 2]> {
    let mut next = if now_ms.saturating_sub(window[0]) >= 10_000 {
        [now_ms, 0]
    } else {
        window
    };
    if next[1] >= 5 {
        return None;
    }
    next[1] += 1;
    Some(next)
}

#[cfg(target_arch = "wasm32")]
pub mod runtime {
    use super::*;
    use worker::*;

    #[durable_object]
    pub struct PublicRoom {
        state: State,
    }

    impl DurableObject for PublicRoom {
        fn new(state: State, _env: Env) -> Self {
            Self { state }
        }

        async fn fetch(&self, req: Request) -> Result<Response> {
            if req.method() != Method::Get
                || req.headers().get("Upgrade")?.as_deref() != Some("websocket")
            {
                return Response::error("WebSocket upgrade required", 426);
            }
            if self.state.get_websockets().len() >= MAX_CONNECTIONS {
                return Response::error("Room is full", 503);
            }
            let pair = WebSocketPair::new()?;
            pair.server
                .serialize_attachment([Date::now().as_millis(), 0_u64])?;
            self.state.accept_web_socket(&pair.server);
            Response::from_websocket(pair.client)
        }

        async fn websocket_message(
            &self,
            ws: WebSocket,
            message: WebSocketIncomingMessage,
        ) -> Result<()> {
            let WebSocketIncomingMessage::String(text) = message else {
                return ws.close(Some(1003), Some("Text messages only"));
            };
            if text.len() > MAX_MESSAGE_BYTES {
                return ws.close(Some(1009), Some("Message too large"));
            }
            if !valid_message(&text) {
                return ws.close(Some(1008), Some("Invalid public message"));
            }
            let window = ws.deserialize_attachment::<[u64; 2]>()?.unwrap_or([0, 5]);
            let Some(next) = admit_message(window, Date::now().as_millis()) else {
                return ws.close(Some(1008), Some("Message rate exceeded"));
            };
            ws.serialize_attachment(next)?;
            for peer in self.state.get_websockets() {
                if peer.send_with_str(&text).is_err() {
                    let _ = peer.close(Some(1011), Some("Connection unavailable"));
                }
            }
            Ok(())
        }

        async fn websocket_close(
            &self,
            ws: WebSocket,
            _code: usize,
            _reason: String,
            _was_clean: bool,
        ) -> Result<()> {
            ws.close(Some(1000), Some("Closed"))
        }

        async fn websocket_error(&self, ws: WebSocket, _error: Error) -> Result<()> {
            ws.close(Some(1011), Some("Connection unavailable"))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn room_routes_are_canonical_and_bounded() {
        assert_eq!(room_from_path("/rooms/demo-1/ws"), Some("demo-1"));
        for path in [
            "/rooms//ws",
            "/rooms/Upper/ws",
            "/rooms/a/b/ws",
            "/rooms/%61/ws",
            "/rooms/../ws",
            "/rooms/a/ws/",
            "/private/demo/ws",
        ] {
            assert_eq!(room_from_path(path), None);
        }
        assert_eq!(
            room_from_path(&format!("/rooms/{}/ws", "a".repeat(33))),
            None
        );
    }

    #[test]
    fn public_text_is_utf8_bounded_and_controls_are_rejected() {
        assert!(valid_message("public test"));
        assert!(valid_message("á\npublic\ttest"));
        assert!(valid_message(&"x".repeat(1024)));
        for invalid in [String::new(), " \n".into(), "x\0y".into(), "á".repeat(513)] {
            assert!(!valid_message(&invalid));
        }
    }

    #[test]
    fn rate_window_survives_serialization_and_rejects_sixth_message() {
        let mut state = [20_000, 0];
        for _ in 0..5 {
            state = admit_message(state, 20_001).unwrap();
        }
        assert_eq!(admit_message(state, 20_002), None);
        assert_eq!(admit_message(state, 30_000), Some([30_000, 1]));
        assert_eq!(admit_message(state, 19_999), None);
    }
}
