//! Offline authentication foundation and the existing Worker health handler.

pub mod gateway_auth;
pub mod public_rooms;

#[cfg(target_arch = "wasm32")]
pub use public_rooms::runtime::PublicRoom;

#[cfg(target_arch = "wasm32")]
use worker::{event, Context, Env, Method, Request, Response, Result};

#[cfg(target_arch = "wasm32")]
#[event(fetch)]
async fn fetch(request: Request, env: Env, _context: Context) -> Result<Response> {
    let path = request.path();
    if path == "/rooms" || path == "/rooms.js" || path.starts_with("/rooms/") {
        if env
            .var("PUBLIC_ROOMS_ENABLED")
            .map(|v| v.to_string())
            .ok()
            .as_deref()
            != Some("true")
        {
            return Response::error("Not found", 404);
        }
        if request.method() != Method::Get {
            return Response::error("Method not allowed", 405);
        }
        if path == "/rooms" {
            let mut response = Response::from_html(include_str!("../static/rooms.html"))?;
            response.headers_mut().set("Cache-Control", "no-store")?;
            response
                .headers_mut()
                .set("Referrer-Policy", "no-referrer")?;
            response.headers_mut().set("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")?;
            return Ok(response);
        }
        if path == "/rooms.js" {
            let mut response = Response::ok(include_str!("../static/rooms.js"))?;
            response
                .headers_mut()
                .set("Content-Type", "text/javascript; charset=utf-8")?;
            response
                .headers_mut()
                .set("X-Content-Type-Options", "nosniff")?;
            response.headers_mut().set("Cache-Control", "no-store")?;
            return Ok(response);
        }
        if let Some(room) = public_rooms::room_from_path(&path) {
            if request.url()?.query().is_some() {
                return Response::error("Query parameters are not supported", 400);
            }
            if request.headers().get("Upgrade")?.as_deref() != Some("websocket") {
                return Response::error("WebSocket upgrade required", 426);
            }
            let origin = request.url()?.origin().ascii_serialization();
            if request.headers().get("Origin")?.as_deref() != Some(origin.as_str()) {
                return Response::error("Same-origin browser required", 403);
            }
            return env
                .durable_object("PUBLIC_ROOMS")?
                .get_by_name(room)?
                .fetch_with_request(request)
                .await;
        }
        return Response::error("Not found", 404);
    }
    match (request.method(), request.path().as_str()) {
        (Method::Get, "/health") => Response::ok("FaroNet edge scaffold ready"),
        (Method::Get, "/") => Response::ok(
            "FaroNet Rust edge scaffold. See /health. Application features are pending.",
        ),
        _ => Response::error("Not found", 404),
    }
}
