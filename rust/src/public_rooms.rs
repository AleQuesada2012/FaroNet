//! Opt-in public topic rooms and their Atom feeds. Never a private mesh endpoint.

pub const MAX_MESSAGE_BYTES: usize = 1024;
pub const MAX_CONNECTIONS: usize = 16;
/// Feed entries kept per topic, and how long any public entry is stored.
pub const MAX_FEED_ENTRIES: usize = 20;
pub const FEED_TTL_MS: u64 = 24 * 60 * 60 * 1000;
/// Stored times are rounded down to the minute to shed timing metadata.
const PUBLISHED_RESOLUTION_MS: u64 = 60_000;

/// (sequence, published minute in Unix ms, public text). No identity or address.
pub type FeedEntry = (u64, u64, String);

pub fn valid_room(room: &str) -> bool {
    !room.is_empty()
        && room.len() <= 32
        && room
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-')
}

pub fn room_from_path(path: &str) -> Option<&str> {
    let room = path.strip_prefix("/rooms/")?.strip_suffix("/ws")?;
    valid_room(room).then_some(room)
}

pub fn feed_room_from_path(path: &str) -> Option<&str> {
    let room = path.strip_prefix("/rooms/")?.strip_suffix("/feed.atom")?;
    valid_room(room).then_some(room)
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
    crate::rate_limit::admit_in_window(window, now_ms, 10_000, 5)
}

/// Drop entries past their TTL and keep at most MAX_FEED_ENTRIES, oldest first.
pub fn prune_feed(entries: &mut Vec<FeedEntry>, now_ms: u64) {
    entries.retain(|entry| now_ms.saturating_sub(entry.1) < FEED_TTL_MS);
    let excess = entries.len().saturating_sub(MAX_FEED_ENTRIES);
    entries.drain(..excess);
}

pub fn append_feed(entries: &mut Vec<FeedEntry>, sequence: u64, now_ms: u64, text: &str) {
    let published = now_ms - now_ms % PUBLISHED_RESOLUTION_MS;
    entries.push((sequence, published, text.to_string()));
    prune_feed(entries, now_ms);
}

/// When the oldest stored entry expires, so an alarm can erase it.
pub fn next_expiry(entries: &[FeedEntry]) -> Option<u64> {
    entries.iter().map(|entry| entry.1 + FEED_TTL_MS).min()
}

/// Escape for XML 1.0 text and attributes; characters XML forbids become U+FFFD.
pub fn xml_text(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&apos;"),
            '\t' | '\n' | '\r' => out.push(c),
            c if c < ' ' || c == '\u{FFFE}' || c == '\u{FFFF}' => out.push('\u{FFFD}'),
            c => out.push(c),
        }
    }
    out
}

/// RFC 3339 UTC timestamp for Atom, from Unix milliseconds.
pub fn rfc3339(ms: u64) -> String {
    let seconds = ms / 1000;
    // Howard Hinnant's days-to-civil algorithm.
    let z = (seconds / 86_400) as i64 + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + i64::from(month <= 2);
    let rest = seconds % 86_400;
    format!(
        "{year:04}-{month:02}-{day:02}T{:02}:{:02}:{:02}Z",
        rest / 3600,
        rest % 3600 / 60,
        rest % 60
    )
}

fn entry_title(text: &str) -> String {
    let line = text.trim().lines().next().unwrap_or_default();
    let title: String = line.chars().take(64).collect();
    if title.len() < line.len() {
        format!("{title}\u{2026}")
    } else {
        title
    }
}

/// One Atom 1.0 feed per public topic, newest entry first.
pub fn atom_feed(origin: &str, room: &str, entries: &[FeedEntry], now_ms: u64) -> String {
    let updated = entries
        .iter()
        .map(|entry| entry.1)
        .max()
        .unwrap_or(now_ms - now_ms % PUBLISHED_RESOLUTION_MS);
    let self_url = xml_text(&format!("{origin}/rooms/{room}/feed.atom"));
    let mut feed = format!(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n\
         <feed xmlns=\"http://www.w3.org/2005/Atom\" xml:lang=\"es\">\n\
         <id>urn:faronet:public-topic:{room}</id>\n\
         <title>Tema público de FaroNet: {room}</title>\n\
         <subtitle>Mensajes explícitamente públicos; cada entrada caduca a las 24 horas.</subtitle>\n\
         <updated>{}</updated>\n\
         <author><name>FaroNet</name></author>\n\
         <link rel=\"self\" type=\"application/atom+xml\" href=\"{self_url}\"/>\n",
        rfc3339(updated)
    );
    for (sequence, published, text) in entries.iter().rev() {
        feed.push_str(&format!(
            "<entry>\n<id>urn:faronet:public-topic:{room}:{sequence}</id>\n\
             <title>{}</title>\n<updated>{}</updated>\n\
             <content type=\"text\">{}</content>\n</entry>\n",
            xml_text(&entry_title(text)),
            rfc3339(*published),
            xml_text(text)
        ));
    }
    feed.push_str("</feed>\n");
    feed
}

#[cfg(target_arch = "wasm32")]
pub mod runtime {
    use super::*;
    use worker::*;

    #[durable_object]
    pub struct PublicRoom {
        state: State,
    }

    impl PublicRoom {
        /// Read the topic's entries, persisting any TTL pruning and the next expiry alarm.
        async fn load_feed(&self, now: u64) -> Result<Vec<FeedEntry>> {
            let storage = self.state.storage();
            let mut entries: Vec<FeedEntry> = storage.get("feed").await?.unwrap_or_default();
            let stored = entries.len();
            prune_feed(&mut entries, now);
            if entries.len() != stored {
                self.save_feed(&entries, now).await?;
            }
            Ok(entries)
        }

        async fn save_feed(&self, entries: &[FeedEntry], now: u64) -> Result<()> {
            let storage = self.state.storage();
            match next_expiry(entries) {
                Some(expiry) => {
                    storage.put("feed", entries).await?;
                    let delay = expiry.saturating_sub(now).max(1);
                    storage
                        .set_alarm(std::time::Duration::from_millis(delay))
                        .await
                }
                None => storage.delete("feed").await.map(|_| ()),
            }
        }

        async fn record(&self, text: &str) -> Result<()> {
            let storage = self.state.storage();
            let now = Date::now().as_millis();
            let sequence: u64 = storage.get("sequence").await?.unwrap_or(0);
            let mut entries = self.load_feed(now).await?;
            append_feed(&mut entries, sequence, now, text);
            storage.put("sequence", sequence + 1).await?;
            self.save_feed(&entries, now).await
        }

        /// Record a public entry and send it to every connection in the topic.
        async fn publish(&self, text: &str) -> Result<()> {
            self.record(text).await?;
            for peer in self.state.get_websockets() {
                if peer.send_with_str(text).is_err() {
                    let _ = peer.close(Some(1011), Some("Conexión no disponible"));
                }
            }
            Ok(())
        }
    }

    impl DurableObject for PublicRoom {
        fn new(state: State, _env: Env) -> Self {
            Self { state }
        }

        async fn fetch(&self, mut req: Request) -> Result<Response> {
            let url = req.url()?;
            // Internal path: only gateway.rs reaches it, after authenticating the
            // Gateway and claiming its nonce. The Worker never forwards it from outside.
            if url.path() == "/gateway-relay" && req.method() == Method::Post {
                let text = req.text().await?;
                if !valid_message(&text) {
                    return Response::error("Mensaje público inválido", 400);
                }
                self.publish(&text).await?;
                return Ok(Response::empty()?.with_status(202));
            }
            if let Some(room) = feed_room_from_path(url.path()) {
                if req.method() != Method::Get {
                    return Response::error("Método no permitido", 405);
                }
                let now = Date::now().as_millis();
                let entries = self.load_feed(now).await?;
                let origin = url.origin().ascii_serialization();
                let mut response = Response::ok(atom_feed(&origin, room, &entries, now))?;
                let headers = response.headers_mut();
                headers.set("Content-Type", "application/atom+xml; charset=utf-8")?;
                headers.set("X-Content-Type-Options", "nosniff")?;
                headers.set("Cache-Control", "public, max-age=30")?;
                return Ok(response);
            }
            if req.method() != Method::Get
                || req.headers().get("Upgrade")?.as_deref() != Some("websocket")
            {
                return Response::error("Se requiere WebSocket", 426);
            }
            if self.state.get_websockets().len() >= MAX_CONNECTIONS {
                return Response::error("La sala está llena", 503);
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
                return ws.close(Some(1003), Some("Solo mensajes de texto"));
            };
            if text.len() > MAX_MESSAGE_BYTES {
                return ws.close(Some(1009), Some("Mensaje demasiado grande"));
            }
            if !valid_message(&text) {
                return ws.close(Some(1008), Some("Mensaje público inválido"));
            }
            let window = ws.deserialize_attachment::<[u64; 2]>()?.unwrap_or([0, 5]);
            let Some(next) = admit_message(window, Date::now().as_millis()) else {
                return ws.close(Some(1008), Some("Demasiados mensajes"));
            };
            ws.serialize_attachment(next)?;
            self.publish(&text).await
        }

        async fn alarm(&self) -> Result<Response> {
            // Erase expired public entries even if nobody reads the feed again.
            self.load_feed(Date::now().as_millis()).await?;
            Response::empty()
        }

        async fn websocket_close(
            &self,
            ws: WebSocket,
            _code: usize,
            _reason: String,
            _was_clean: bool,
        ) -> Result<()> {
            ws.close(Some(1000), Some("Cerrada"))
        }

        async fn websocket_error(&self, ws: WebSocket, _error: Error) -> Result<()> {
            ws.close(Some(1011), Some("Conexión no disponible"))
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
    fn feed_routes_are_canonical() {
        assert_eq!(
            feed_room_from_path("/rooms/demo-1/feed.atom"),
            Some("demo-1")
        );
        for path in [
            "/rooms//feed.atom",
            "/rooms/Up/feed.atom",
            "/rooms/a/b/feed.atom",
            "/rooms/demo/feed",
        ] {
            assert_eq!(feed_room_from_path(path), None);
        }
    }

    #[test]
    fn feed_keeps_twenty_unexpired_entries_on_minute_resolution() {
        let mut entries = Vec::new();
        for sequence in 0..25 {
            append_feed(&mut entries, sequence, 1_000_000 + sequence * 1000, "x");
        }
        assert_eq!(entries.len(), MAX_FEED_ENTRIES);
        assert_eq!(entries[0].0, 5);
        assert!(entries.iter().all(|entry| entry.1 % 60_000 == 0));
        assert_eq!(next_expiry(&entries), Some(960_000 + FEED_TTL_MS));
        prune_feed(&mut entries, 960_000 + FEED_TTL_MS);
        assert_eq!(
            entries.iter().map(|e| e.0).collect::<Vec<_>>(),
            [20, 21, 22, 23, 24]
        );
        prune_feed(&mut entries, 1_020_000 + FEED_TTL_MS);
        assert!(entries.is_empty());
        assert_eq!(next_expiry(&entries), None);
    }

    #[test]
    fn rfc3339_handles_epoch_leap_day_and_large_values() {
        assert_eq!(rfc3339(0), "1970-01-01T00:00:00Z");
        assert_eq!(rfc3339(951_782_400_000), "2000-02-29T00:00:00Z");
        assert_eq!(rfc3339(1_000_000_000_999), "2001-09-09T01:46:40Z");
        assert_eq!(rfc3339(1_793_577_599_000), "2026-11-01T23:59:59Z");
    }

    #[test]
    fn atom_escapes_markup_and_orders_newest_first() {
        let entries = vec![
            (0, 60_000, "first".to_string()),
            (
                1,
                120_000,
                "<img src=x onerror=\"alert(1)\"> & 'more'\u{FFFE}".to_string(),
            ),
        ];
        let feed = atom_feed("https://edge.example", "demo", &entries, 180_000);
        assert!(feed.starts_with("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<feed xmlns=\"http://www.w3.org/2005/Atom\" xml:lang=\"es\">"));
        assert!(feed.contains(
            "&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; &apos;more&apos;\u{FFFD}"
        ));
        assert!(!feed.contains("<img"));
        assert!(feed.contains("<updated>1970-01-01T00:02:00Z</updated>"));
        assert!(feed.find(":demo:1</id>").unwrap() < feed.find(":demo:0</id>").unwrap());
        assert!(feed.contains("href=\"https://edge.example/rooms/demo/feed.atom\""));
        let empty = atom_feed("https://edge.example", "quiet", &[], 185_000);
        assert!(
            !empty.contains("<entry>") && empty.contains("<updated>1970-01-01T00:03:00Z</updated>")
        );
        let long = "y".repeat(100);
        assert!(atom_feed("o", "t", &[(0, 0, long)], 0)
            .contains(&format!("<title>{}\u{2026}</title>", "y".repeat(64))));
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
